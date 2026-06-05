"""Training run manager — spawns the QLoRA subprocess and tracks its lifecycle.

Why a subprocess (not a thread)?
  * Clean GPU teardown — when the run ends, the OS reclaims *all* VRAM. A
    long-lived in-process trainer tends to leak fragments on a 16 GB card.
  * Hard cancel — we can SIGTERM the run without corrupting the API process.

Contract with ``scripts/train_qlora.py`` (the child):
  * reads ``runs/<id>/config.json``
  * appends one JSON object per log step to ``runs/<id>/metrics.jsonl``
  * writes a terminal ``runs/<id>/status.json`` ({status, adapter_path, metrics,
    error}) just before exit.

The API tails ``metrics.jsonl`` over a WebSocket (see router); a monitor thread
here waits for process exit and finalizes the DB (creating the new
:class:`ModelVersion` node on success).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DBSession

from ...core.config import BACKEND_DIR, settings
from ...core.db import engine as db_engine
from ...core.models import ModelVersion, Project, RunStatus, TrainingRun
from ..inference.engine import engine as inference_engine
from ..versioning import service as versioning
from . import dataset

TRAIN_SCRIPT = BACKEND_DIR / "scripts" / "train_qlora.py"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TrainingManager:
    def __init__(self) -> None:
        self._procs: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    # ── paths ──
    def run_dir(self, run_id: str) -> Path:
        d = settings.runs_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def metrics_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "metrics.jsonl"

    def status_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "status.json"

    # ── lifecycle ──
    def prepare(self, db: DBSession, run: TrainingRun) -> TrainingRun:
        """Build the dataset + config.json. Returns the run with paths filled in."""
        project = db.get(Project, run.project_id)
        if not project:
            raise ValueError("Project not found")

        examples = dataset.collect_examples(
            db, run.project_id,
            session_ids=run.config.get("session_ids"),
            task_id=run.config.get("task_id"),
            only_corrected=run.config.get("only_corrected", False),
        )
        ds_path = settings.datasets_dir / f"{run.id}.jsonl"
        n = dataset.write_jsonl(examples, ds_path)

        parent_adapter = None
        if run.parent_version_id:
            parent = db.get(ModelVersion, run.parent_version_id)
            if parent and not parent.is_base:
                parent_adapter = parent.adapter_path

        run_dir = self.run_dir(run.id)
        out_dir = settings.adapters_dir / run.id
        cfg = {
            "run_id": run.id,
            "base_model": project.base_model_local_path or project.base_model_repo,
            "resume_adapter_path": parent_adapter,
            "dataset_path": str(ds_path),
            "output_dir": str(out_dir),
            "metrics_path": str(self.metrics_path(run.id)),
            "status_path": str(self.status_path(run.id)),
            "log_path": str(run_dir / "train.log"),
            "hf_cache": str(settings.hf_home),
            # Disk spillover dir + how much CPU RAM the offload fallback may use
            # (the box has 128 GB → generous default).
            "offload_folder": str(settings.offload_dir / run.id),
            "cpu_offload_gb": 96,
            "num_examples": n,
            **project.default_train_config,
            **(run.config.get("hyperparams") or {}),
        }
        (run_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))

        run.dataset_path = str(ds_path)
        run.num_examples = n
        run.metrics_path = str(self.metrics_path(run.id))
        run.log_path = str(run_dir / "train.log")
        run.config = {**run.config, "resolved": cfg}
        run.status = RunStatus.preparing
        # rough total-step estimate for the progress bar
        run.progress = {"total_steps": self._estimate_steps(n, cfg), "step": 0}
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def _estimate_steps(n_examples: int, cfg: dict[str, Any]) -> int:
        bs = max(1, int(cfg.get("per_device_batch_size", 1)))
        ga = max(1, int(cfg.get("grad_accum_steps", 1)))
        epochs = max(1, int(cfg.get("epochs", 1)))
        per_epoch = math.ceil(n_examples / (bs * ga)) if n_examples else 0
        return per_epoch * epochs

    def launch(self, run_id: str) -> None:
        """Free VRAM, spawn the trainer, and start the monitor thread."""
        with self._lock:
            if run_id in self._procs and self._procs[run_id].poll() is None:
                return  # already running
        # Give the whole GPU to training: unload AND freeze so a warmup/chat
        # can't re-load a model mid-run and steal VRAM (which causes bitsandbytes
        # "Some modules are dispatched on the CPU or the disk").
        inference_engine.freeze()

        run_dir = self.run_dir(run_id)
        cfg_path = run_dir / "config.json"
        log_file = open(run_dir / "train.log", "a", encoding="utf-8")
        env = {"HF_HOME": str(settings.hf_home), "TOKENIZERS_PARALLELISM": "false"}
        import os
        proc = subprocess.Popen(
            [sys.executable, str(TRAIN_SCRIPT), "--config", str(cfg_path)],
            cwd=str(BACKEND_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env={**os.environ, **env},
        )
        with self._lock:
            self._procs[run_id] = proc

        with DBSession(db_engine) as db:
            run = db.get(TrainingRun, run_id)
            if run:
                run.status = RunStatus.running
                run.pid = proc.pid
                run.started_at = _now()
                db.add(run)
                db.commit()

        threading.Thread(target=self._monitor, args=(run_id, proc), daemon=True).start()

    def _monitor(self, run_id: str, proc: subprocess.Popen) -> None:
        try:
            self._finalize(run_id, proc)
        finally:
            # Re-enable inference now that the GPU is free again.
            inference_engine.unfreeze()

    def _finalize(self, run_id: str, proc: subprocess.Popen) -> None:
        proc.wait()
        with self._lock:
            self._procs.pop(run_id, None)
        status_file = self.status_path(run_id)
        result: dict[str, Any] = {}
        if status_file.exists():
            try:
                result = json.loads(status_file.read_text())
            except Exception:
                result = {}

        with DBSession(db_engine) as db:
            run = db.get(TrainingRun, run_id)
            if not run:
                return
            if run.status == RunStatus.cancelled:
                run.finished_at = _now()
                db.add(run)
                db.commit()
                return

            ok = proc.returncode == 0 and result.get("status") == "completed"
            if ok:
                project = db.get(Project, run.project_id)
                version = versioning.create_child(
                    db,
                    run.project_id,
                    run.parent_version_id,
                    label=run.name,
                    adapter_path=result.get("adapter_path"),
                    training_run_id=run.id,
                    notes=f"Fine-tuned from {run.num_examples} examples",
                    metrics=result.get("metrics", {}),
                )
                run.result_version_id = version.id
                run.metrics = result.get("metrics", {})
                run.status = RunStatus.completed
                # Auto-activate the freshly trained version.
                if project:
                    versioning.set_active(db, project, version.id)
            else:
                run.status = RunStatus.failed
                run.error = result.get("error") or f"Trainer exited with code {proc.returncode}"
            run.finished_at = _now()
            db.add(run)
            db.commit()

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            proc = self._procs.get(run_id)
        if not proc:
            return False
        proc.terminate()
        with DBSession(db_engine) as db:
            run = db.get(TrainingRun, run_id)
            if run:
                run.status = RunStatus.cancelled
                run.finished_at = _now()
                db.add(run)
                db.commit()
        return True

    def is_running(self, run_id: str) -> bool:
        with self._lock:
            proc = self._procs.get(run_id)
            return bool(proc and proc.poll() is None)


manager = TrainingManager()
