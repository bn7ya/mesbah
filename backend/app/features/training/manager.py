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
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DBSession
from sqlmodel import select

from ...core import hardware
from ...core.config import BACKEND_DIR, settings
from ...core.db import engine as db_engine
from ...core.models import ModelVersion, Project, RunStatus, TrainingRun
from ..inference.engine import engine as inference_engine
from ..versioning import service as versioning
from . import dataset

TRAIN_SCRIPT = BACKEND_DIR / "scripts" / "train_qlora.py"
SCRATCH_SCRIPT = BACKEND_DIR / "scripts" / "train_scratch.py"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _free_port() -> int:
    """An ephemeral free TCP port for the single-process DeepSpeed rendezvous."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pid_alive(pid: Optional[int]) -> bool:
    """True if a process with ``pid`` currently exists.

    An orphaned trainer is reparented to init but keeps its PID, so a plain
    ``kill(pid, 0)`` existence probe is enough to know if it is still running.
    """
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OSError):
        return False
    return True


class TrainingBusyError(RuntimeError):
    """Raised when a run is asked to launch while another already owns the GPU.

    A single-GPU box can only train one model at a time (CLAUDE.md: "one model
    resident at a time"). Without this, two trainer subprocesses co-reside and
    fight over VRAM until one OOMs — the failure this guard prevents.
    """

    def __init__(self, active_run_id: str) -> None:
        self.active_run_id = active_run_id
        super().__init__(
            f"Another training run ({active_run_id}) is already using the GPU(s). "
            "Only one run can train at a time — wait for it to finish or cancel "
            "it first."
        )


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

    def log_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "train.log"

    # ── lifecycle ──
    def prepare(self, db: DBSession, run: TrainingRun) -> TrainingRun:
        """Build the dataset + config.json. Returns the run with paths filled in.

        Two flavours, by ``project.kind``:
          * ``finetune`` — QLoRA on a pretrained base; dataset = approved chat
            turns, written to the project's data folder.
          * ``scratch`` — full training of a custom architecture; the corpus is
            an HF dataset ingested by the subprocess, so there's no local JSONL to
            build here. The architecture spec rides along in default_train_config.
        """
        project = db.get(Project, run.project_id)
        if not project:
            raise ValueError("Project not found")
        is_scratch = project.kind == "scratch"

        settings.ensure_project_dirs(project.id)
        run_dir = self.run_dir(run.id)
        out_dir = settings.project_versions_dir(project.id) / run.id
        ds_path = settings.project_data_dir(project.id) / f"{run.id}.jsonl"

        # Merge project defaults + per-run overrides; injected paths win last.
        merged: dict[str, Any] = {
            **project.default_train_config,
            **(run.config.get("hyperparams") or {}),
        }
        # Hardware-derived offload budget (detected RAM), not a fixed 96 GB.
        hw = hardware.train_defaults("scratch" if is_scratch else "finetune")
        merged.setdefault("cpu_offload_gb", hw["cpu_offload_gb"])

        if is_scratch:
            # No chat dataset; the trainer pulls dataset_repo from the config.
            n = int(merged.get("max_train_samples") or 0)
            base_model = project.base_model_repo
            parent_adapter = None
            # ZeRO-Infinity offload knobs: estimate the off-GPU (host RAM) footprint
            # so "auto" can choose cpu vs nvme, and point NVMe spill at the run's
            # project offload dir.
            merged.setdefault("offload_target", "auto")
            merged["nvme_path"] = str(settings.project_offload_dir(project.id) / run.id)
            try:
                from ..architect import service as architect
                from ..architect.schemas import ArchitectureSpec
                spec = ArchitectureSpec(**(merged.get("architecture") or {}))
                merged.setdefault("est_host_ram_gb",
                                  architect.estimate(spec).memory.host_ram_gb)
            except Exception:
                pass
        else:
            use_corrections = bool(run.config.get("use_corrections", True))
            if use_corrections:
                examples = dataset.collect_examples(
                    db, run.project_id,
                    session_ids=run.config.get("session_ids"),
                    task_id=run.config.get("task_id"),
                    only_corrected=run.config.get("only_corrected", False),
                )
                n = dataset.write_jsonl(examples, ds_path)
            else:
                n = 0
            # Optional HF datasets trained alongside (or instead of) corrections.
            merged["datasets"] = run.config.get("datasets") or []
            merged["use_corrections"] = use_corrections
            base_model = project.base_model_local_path or project.base_model_repo
            parent_adapter = None
            if run.parent_version_id:
                parent = db.get(ModelVersion, run.parent_version_id)
                if parent and not parent.is_base:
                    parent_adapter = parent.adapter_path

        cfg = {
            **merged,
            # ── authoritative, never overridable by config ──
            "run_id": run.id,
            "kind": project.kind,
            "base_model": base_model,
            "resume_adapter_path": parent_adapter,
            "dataset_path": str(ds_path),
            "output_dir": str(out_dir),
            "metrics_path": str(self.metrics_path(run.id)),
            "status_path": str(self.status_path(run.id)),
            "log_path": str(run_dir / "train.log"),
            "hf_cache": str(settings.hf_home),
            "offload_folder": str(settings.project_offload_dir(project.id) / run.id),
            # Real host RAM so the cpu-vs-nvme offload decision isn't a fixed 100 GB.
            "host_ram_gb": settings.resolved_ram_gb(),
            "num_examples": n,
            # GPUs the trainer may use (drives CUDA_VISIBLE_DEVICES in launch()).
            "gpu_indices": [g["index"] for g in hardware.effective_gpus()],
            "num_gpus": len(hardware.effective_gpus()),
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
        # HF datasets add examples the corrections count doesn't know about; use
        # their max_samples caps as a rough contribution. The trainer corrects
        # total_steps at on_train_begin anyway.
        for spec in (cfg.get("datasets") or []):
            try:
                n_examples += int(spec.get("max_samples") or 0)
            except (TypeError, ValueError):
                pass
        per_epoch = math.ceil(n_examples / (bs * ga)) if n_examples else 0
        return per_epoch * epochs

    def launch(self, run_id: str) -> None:
        """Free VRAM, spawn the trainer, and start the monitor thread.

        Raises :class:`TrainingBusyError` if another run already owns the GPU.
        """
        with self._lock:
            if run_id in self._procs and self._procs[run_id].poll() is None:
                return  # already running
        # One GPU → one trainer. Refuse to start while another run is resident,
        # otherwise the two co-resident trainers fight over VRAM and OOM (the exact
        # failure mode this guards against).
        busy = self.active_run_id(exclude=run_id)
        if busy:
            raise TrainingBusyError(busy)
        # Give the whole GPU to training: unload AND freeze so a warmup/chat
        # can't re-load a model mid-run and steal VRAM (which causes bitsandbytes
        # "Some modules are dispatched on the CPU or the disk").
        inference_engine.freeze()

        run_dir = self.run_dir(run_id)
        cfg_path = run_dir / "config.json"
        # Pick the trainer by project kind (recorded in config.json): full
        # from-scratch training vs QLoRA fine-tuning.
        script = TRAIN_SCRIPT
        scratch_paged = False
        gpu_indices: list[int] = []
        try:
            run_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            if run_cfg.get("kind") == "scratch":
                script = SCRATCH_SCRIPT
                scratch_paged = bool(run_cfg.get("paged_training"))
            gpu_indices = [int(i) for i in (run_cfg.get("gpu_indices") or [])]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
        if not gpu_indices:
            gpu_indices = [g["index"] for g in hardware.effective_gpus()]
        log_file = open(run_dir / "train.log", "a", encoding="utf-8")
        env = {"HF_HOME": str(settings.hf_home), "TOKENIZERS_PARALLELISM": "false"}
        # Restrict the trainer to the user-selected GPU(s). Inside the child the
        # visible devices are renumbered 0..N-1, so device_map logic stays simple.
        if gpu_indices:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in gpu_indices)
        # ZeRO-Infinity (from-scratch paged) runs as a single-process distributed
        # job; set the env DeepSpeed/HF Trainer need so no `deepspeed` CLI launcher
        # is required. (Alternative: `deepspeed --num_gpus=1 scripts/train_scratch.py`.)
        if scratch_paged:
            env.update({
                "RANK": "0", "LOCAL_RANK": "0", "WORLD_SIZE": "1",
                "MASTER_ADDR": "127.0.0.1", "MASTER_PORT": str(_free_port()),
            })
        import os
        proc = subprocess.Popen(
            [sys.executable, str(script), "--config", str(cfg_path)],
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
        self._apply_result(
            run_id,
            proc_ok=proc.returncode == 0,
            fail_reason=f"Trainer exited with code {proc.returncode}",
        )

    def _apply_result(self, run_id: str, *, proc_ok: bool, fail_reason: str) -> None:
        """Read the child's ``status.json`` and write the terminal DB state.

        Shared by the live monitor (``_finalize``) and startup recovery
        (``_readopt``) so a run finalizes identically no matter which path
        observes the process exit.
        """
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

            ok = proc_ok and result.get("status") == "completed"
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
                run.error = result.get("error") or fail_reason
            run.finished_at = _now()
            db.add(run)
            db.commit()

    # ── crash / reload recovery ──
    def reconcile_orphans(self) -> None:
        """Recover runs left non-terminal by a worker restart or crash.

        The live monitor thread runs *inside* the API worker. If that worker is
        replaced (``uvicorn --reload``) or crashes mid-run, the training
        subprocess keeps going and writes ``status.json``, but nothing updates
        the DB — the run is stuck ``running``/``preparing`` forever. On startup
        we re-adopt every such run: wait for its (possibly still-alive) process,
        then finalize from ``status.json`` exactly as the monitor would.
        """
        with DBSession(db_engine) as db:
            stmt = select(TrainingRun).where(
                TrainingRun.status.in_([RunStatus.running, RunStatus.preparing])
            )
            orphans = [(r.id, r.pid) for r in db.exec(stmt).all()]
        for run_id, pid in orphans:
            if self.is_running(run_id):
                continue  # this worker already owns a live monitor for it
            threading.Thread(
                target=self._readopt, args=(run_id, pid), daemon=True
            ).start()

    def _readopt(self, run_id: str, pid: Optional[int]) -> None:
        """Wait for an orphaned trainer to exit, then finalize it."""
        try:
            while _pid_alive(pid):
                time.sleep(2.0)
            # Small grace so the child can flush status.json after exiting.
            time.sleep(1.0)
            self._apply_result(
                run_id,
                proc_ok=True,  # no returncode to trust → defer to status.json
                fail_reason="Training process was lost (API restarted or crashed "
                            "mid-run) and left no completion marker.",
            )
        finally:
            inference_engine.unfreeze()

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

    def active_run_id(self, exclude: Optional[str] = None) -> Optional[str]:
        """The run_id of any training run currently occupying the GPU, else None.

        Two sources, so a second trainer can never co-resident-OOM the card:
          * a live subprocess this worker owns (``self._procs``);
          * an orphan from a previous worker — a DB run still ``running``/
            ``preparing`` whose recorded PID is still alive (this is exactly how a
            stale run can keep holding VRAM after a ``uvicorn --reload``).
        """
        with self._lock:
            for rid, proc in self._procs.items():
                if rid != exclude and proc.poll() is None:
                    return rid
        with DBSession(db_engine) as db:
            stmt = select(TrainingRun).where(
                TrainingRun.status.in_([RunStatus.running, RunStatus.preparing])
            )
            for run in db.exec(stmt).all():
                if run.id != exclude and _pid_alive(run.pid):
                    return run.id
        return None


manager = TrainingManager()
