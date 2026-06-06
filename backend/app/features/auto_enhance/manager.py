"""Auto-enhance manager — the closed self-improvement loop orchestrator.

Why a thread (not a subprocess, unlike training)?
  * The loop *uses* the resident inference engine for every phase (ask, answer,
    evaluate, correct). A subprocess would need its own copy of the model.
  * The only GPU-exclusive phase is training, which the loop delegates to the
    existing training subprocess (and blocks while it runs).

Lifecycle: a daemon thread runs the whole G-generation loop. Per-step fresh
``DBSession``. Live progress is appended to ``loops/<id>/events.jsonl`` (tailed by
the WebSocket); status lives on the ``AutoEnhanceLoop`` row. Only ONE loop runs at
a time (single GPU). A loop left non-terminal by a restart is marked ``failed`` —
its worker thread is gone and the generation phases cannot be re-adopted.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DBSession
from sqlmodel import select

from ...core.config import settings
from ...core.db import engine as db_engine
from ...core.models import (AutoEnhanceLoop, Message, MessageRole, Project,
                            RunStatus, TrainingRun)
from ...core.models import Session as ChatSession
from ..inference.engine import ModelRuntimeUnavailable
from ..inference.engine import engine as inference_engine
from ..inference.service import (build_correction_messages, build_messages,
                                 resolve_weights)
from ..sessions import service as sessions_service
from ..training.manager import manager as training_manager
from . import service

TERMINAL = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AutoEnhanceManager:
    """Runs the single active auto-enhance loop in a daemon thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_loop_id: Optional[str] = None
        self._cancel: Optional[threading.Event] = None
        self._thread: Optional[threading.Thread] = None

    # ── paths ──
    def loop_dir(self, loop_id: str) -> Path:
        d = settings.loops_dir / loop_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def events_path(self, loop_id: str) -> Path:
        return self.loop_dir(loop_id) / "events.jsonl"

    # ── public API ──
    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def busy_reason(self) -> Optional[str]:
        """Why a new loop can't start right now, or None if the GPU is free."""
        if self.is_running():
            return "An auto-enhance loop is already running."
        if inference_engine.frozen:
            return "A training run is currently using the GPU."
        return None

    def start(self, loop_id: str) -> None:
        """Spawn the worker thread for ``loop_id`` (returns immediately)."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("An auto-enhance loop is already running.")
            self._active_loop_id = loop_id
            self._cancel = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(loop_id,), daemon=True)
            self._thread.start()

    def cancel(self, loop_id: str) -> bool:
        with self._lock:
            if self._active_loop_id != loop_id or not self._cancel:
                return False
            self._cancel.set()
        # Also kill an in-flight training subprocess for this loop, if any.
        with DBSession(db_engine) as db:
            loop = db.get(AutoEnhanceLoop, loop_id)
            run_id = (loop.progress or {}).get("current_run_id") if loop else None
        if run_id:
            training_manager.cancel(run_id)
        return True

    # ── progress / status persistence ──
    def _emit(self, loop_id: str, etype: str, **data: Any) -> None:
        """Append one progress event (best-effort) to events.jsonl."""
        try:
            payload = {"ts": time.time(), "type": etype, **data}
            with self.events_path(loop_id).open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _set_progress(self, loop_id: str, **fields: Any) -> None:
        with DBSession(db_engine) as db:
            loop = db.get(AutoEnhanceLoop, loop_id)
            if loop:
                loop.progress = {**(loop.progress or {}), **fields}
                db.add(loop)
                db.commit()

    def _set_status(self, loop_id: str, status: RunStatus, error: Optional[str] = None,
                    finished: bool = False, started: bool = False) -> None:
        with DBSession(db_engine) as db:
            loop = db.get(AutoEnhanceLoop, loop_id)
            if not loop:
                return
            loop.status = status
            if error is not None:
                loop.error = error
            if started:
                loop.started_at = _now()
                loop.pid = os.getpid()
            if finished:
                loop.finished_at = _now()
            db.add(loop)
            db.commit()

    def _cancelled(self) -> bool:
        return bool(self._cancel and self._cancel.is_set())

    # ── the loop ──
    def _run(self, loop_id: str) -> None:
        self._set_status(loop_id, RunStatus.running, started=True)
        try:
            with DBSession(db_engine) as db:
                loop = db.get(AutoEnhanceLoop, loop_id)
                cfg = dict(loop.config or {}) if loop else {}
            generations = int(cfg.get("generations", settings.auto_enhance_generations))
            turns = int(cfg.get("turns_per_generation", settings.auto_enhance_turns_per_generation))
            thresholds = cfg.get("thresholds") or settings.auto_enhance_thresholds
            max_rounds = int(cfg.get("max_correction_rounds", settings.auto_enhance_max_correction_rounds))
            topic_source = cfg.get("topic_source", "tasks")
            ask_prompt = cfg.get("ask_prompt") or settings.default_ask_prompt
            eval_prompt = cfg.get("eval_prompt") or settings.default_eval_prompt
            scale = settings.auto_enhance_score_scale

            gen_results: list[dict[str, Any]] = []
            for g in range(1, generations + 1):
                if self._cancelled():
                    break
                self._emit(loop_id, "generation_start", generation=g)
                self._set_progress(loop_id, generation=g, turn=0, phase="generating")

                # Resolve the CURRENT active version fresh — picks up a version the
                # previous generation just trained + activated.
                with DBSession(db_engine, expire_on_commit=False) as db:
                    loop = db.get(AutoEnhanceLoop, loop_id)
                    project = db.get(Project, loop.project_id)
                    base_id, adapter_path = resolve_weights(db, project, None)
                    loop_session = service.create_loop_session(db, project, g)
                    session_id = loop_session.id

                self._ensure_loaded_when_ready(base_id, adapter_path)

                summary = {"generation": g, "approved": 0, "total": 0, "score_sums": {}}
                for t in range(1, turns + 1):
                    if self._cancelled():
                        break
                    self._run_turn(loop_id, session_id, g, t, thresholds, max_rounds,
                                   ask_prompt, eval_prompt, topic_source, scale, summary)

                avg = self._summary_avg(summary)
                self._emit(loop_id, "generation_done", generation=g,
                           approved=summary["approved"], total=summary["total"], avg_scores=avg)
                if self._cancelled():
                    break

                # ── train on this generation's passing turns, then continue on the new tip
                run_id = self._train_generation(loop_id, session_id, g, cfg.get("hyperparams") or {})
                version_id = self._await_training(loop_id, run_id) if run_id else None
                gen_results.append({"generation": g, "run_id": run_id, "version_id": version_id,
                                    "approved": summary["approved"], "total": summary["total"],
                                    "avg_scores": avg})
                self._record_results(loop_id, gen_results)

            if self._cancelled():
                self._set_status(loop_id, RunStatus.cancelled, finished=True)
                self._emit(loop_id, "loop_done", status="cancelled", generations=len(gen_results))
            else:
                self._set_status(loop_id, RunStatus.completed, finished=True)
                self._emit(loop_id, "loop_done", status="completed", generations=len(gen_results),
                           versions=[r["version_id"] for r in gen_results])
        except Exception as exc:  # noqa: BLE001 — any failure ends the loop cleanly
            err = f"{exc}\n{traceback.format_exc()}"
            self._set_status(loop_id, RunStatus.failed, error=str(exc), finished=True)
            self._emit(loop_id, "error", message=str(exc))
            # keep full traceback in the log dir for debugging
            try:
                (self.loop_dir(loop_id) / "error.log").write_text(err, encoding="utf-8")
            except Exception:
                pass
        finally:
            with self._lock:
                self._active_loop_id = None
                self._cancel = None
                self._thread = None

    def _run_turn(self, loop_id: str, session_id: str, g: int, t: int,
                  thresholds: dict, max_rounds: int, ask_prompt: str, eval_prompt: str,
                  topic_source: str, scale: int, summary: dict) -> None:
        self._emit(loop_id, "turn_start", generation=g, turn=t)
        self._set_progress(loop_id, generation=g, turn=t, phase="asking")

        # (a) ask — build context, then generate the next question OUTSIDE the DB txn
        with DBSession(db_engine, expire_on_commit=False) as db:
            loop = db.get(AutoEnhanceLoop, loop_id)
            project = db.get(Project, loop.project_id)
            hist = sessions_service.history(db, session_id)
            task_seed = service.pick_topic_seed(db, project) if topic_source == "tasks" else None
            ask_msgs = service.build_ask_messages(hist, task_seed, ask_prompt)
        question = service.strip_think(
            inference_engine.generate(ask_msgs, temperature=0.9, max_new_tokens=256,
                                      enable_thinking=False))
        if not question:
            question = "اشرح فكرة مهمة من اختيارك بوضوح ودقة."
        self._emit(loop_id, "ask", generation=g, turn=t, text=question)

        # (b) answer — persist the question, build the answer context, generate outside the txn
        self._set_progress(loop_id, phase="answering")
        with DBSession(db_engine, expire_on_commit=False) as db:
            sessions_service.add_message(db, session_id, MessageRole.user, question)
            session = db.get(ChatSession, session_id)
            full = sessions_service.history(db, session_id)
            prior = full[:-1]                       # everything before the just-added question
            answer_msgs = build_messages(session, prior, question)
        answer = service.strip_think(inference_engine.generate(answer_msgs, enable_thinking=False))
        with DBSession(db_engine, expire_on_commit=False) as db:
            answer_msg = sessions_service.add_message(db, session_id, MessageRole.assistant, answer)
            answer_id = answer_msg.id
        self._emit(loop_id, "answer", generation=g, turn=t, message_id=answer_id, text=answer)

        # (c) evaluate
        self._set_progress(loop_id, phase="evaluating")
        scores = self._evaluate(eval_prompt, question, answer, scale)
        self._emit(loop_id, "evaluation", generation=g, turn=t, round=0, scores=scores)

        # (d) correct ↔ re-evaluate until pass or max rounds
        rounds = 0
        while (not service.scores_pass(scores, thresholds)
               and rounds < max_rounds and not self._cancelled()):
            rounds += 1
            self._set_progress(loop_id, phase=f"correcting (round {rounds})")
            with DBSession(db_engine, expire_on_commit=False) as db:
                answer_msg = db.get(Message, answer_id)
                prior = [m for m in sessions_service.history(db, session_id)
                         if m.order_index < answer_msg.order_index]
                corr_msgs = build_correction_messages(
                    settings.default_correction_prompt, prior, answer_msg.content,
                    settings.correction_trigger_text)
            improved = service.strip_think(inference_engine.generate(corr_msgs, enable_thinking=False))
            if improved:
                with DBSession(db_engine, expire_on_commit=False) as db:
                    answer_msg = db.get(Message, answer_id)
                    sessions_service.apply_self_correction(
                        db, answer_msg, improved, settings.default_correction_prompt)
                answer = improved
            self._emit(loop_id, "correction", generation=g, turn=t, round=rounds, text=answer)
            scores = self._evaluate(eval_prompt, question, answer, scale)
            self._emit(loop_id, "evaluation", generation=g, turn=t, round=rounds, scores=scores)

        # (e) quality gate — auto-approve ONLY a passing answer
        passed = service.scores_pass(scores, thresholds)
        with DBSession(db_engine, expire_on_commit=False) as db:
            answer_msg = db.get(Message, answer_id)
            if answer_msg:
                if passed:
                    sessions_service.set_flags(db, answer_msg, approved=True, include_in_training=True)
                meta = dict(answer_msg.meta or {})
                meta.update(auto_enhance=True, loop_id=loop_id, generation=g, turn=t,
                            scores=scores, rounds=rounds)
                answer_msg.meta = meta
                db.add(answer_msg)
                db.commit()

        # (f) tally
        summary["total"] += 1
        if passed:
            summary["approved"] += 1
        for k, v in scores.items():
            summary["score_sums"][k] = summary["score_sums"].get(k, 0) + v
        self._emit(loop_id, "turn_done", generation=g, turn=t, approved=passed, scores=scores, rounds=rounds)

    def _evaluate(self, eval_prompt: str, question: str, answer: str, scale: int) -> dict[str, float]:
        """Generate + parse scores. Retry once on parse failure, else fail (all 0)."""
        msgs = service.build_eval_messages(eval_prompt, question, answer)
        raw = inference_engine.generate(msgs, temperature=0.0, max_new_tokens=512,
                                        enable_thinking=False)
        scores = service.parse_scores(raw, scale)
        if scores is None:
            retry = list(msgs) + [{"role": "user", "content": "أعد JSON فقط بالمفاتيح الأربعة."}]
            raw2 = inference_engine.generate(retry, temperature=0.0, max_new_tokens=512,
                                             enable_thinking=False)
            scores = service.parse_scores(raw2, scale)
        if scores is None:
            # conservative: an unparseable evaluation must NOT auto-approve
            return {k: 0.0 for k in service.SCORE_KEYS}
        return scores

    # ── training integration (the closed-loop hinge) ──
    def _train_generation(self, loop_id: str, session_id: str, g: int,
                          hyperparams: dict) -> Optional[str]:
        with DBSession(db_engine, expire_on_commit=False) as db:
            loop = db.get(AutoEnhanceLoop, loop_id)
            project = db.get(Project, loop.project_id)
            run = TrainingRun(
                project_id=loop.project_id,
                name=f"{loop.name} · جيل {g}",
                parent_version_id=project.active_version_id,
                config={"session_ids": [session_id], "task_id": None,
                        "only_corrected": False, "hyperparams": hyperparams},
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run = training_manager.prepare(db, run)
            run_id = run.id
            n = run.num_examples

        if n == 0:
            self._emit(loop_id, "training_skipped", generation=g, reason="no approved examples")
            return None

        self._set_progress(loop_id, phase="training", current_run_id=run_id)
        self._emit(loop_id, "training_start", generation=g, run_id=run_id, num_examples=n)
        training_manager.launch(run_id)   # freezes + unloads the engine
        return run_id

    def _await_training(self, loop_id: str, run_id: str) -> Optional[str]:
        """Block (no generation — engine is frozen) until the run is terminal."""
        while not self._cancelled():
            with DBSession(db_engine) as db:
                run = db.get(TrainingRun, run_id)
                if not run:
                    return None
                status, version_id, error, progress = (
                    run.status, run.result_version_id, run.error, run.progress)
            self._emit(loop_id, "training_status", run_id=run_id, status=status.value,
                       progress=progress)
            if status in TERMINAL:
                if status == RunStatus.completed:
                    return version_id
                raise RuntimeError(f"training {status.value}: {error or 'unknown error'}")
            time.sleep(2.0)
        # cancelled mid-training
        training_manager.cancel(run_id)
        return None

    def _ensure_loaded_when_ready(self, base_id: str, adapter_path: Optional[str]) -> None:
        """Load the model, waiting out a lingering training freeze (race-safe).

        After a generation's training run, the monitor thread sets the run
        ``completed`` (which unblocks ``_await_training``) and only THEN
        ``unfreeze()``s in its finally. So briefly the engine may still be frozen
        when the next generation starts — wait it out instead of erroring.
        """
        deadline = time.time() + 60
        while not self._cancelled():
            try:
                inference_engine.ensure_loaded(base_id, adapter_path)
                return
            except ModelRuntimeUnavailable:
                if not inference_engine.frozen or time.time() > deadline:
                    raise
                time.sleep(0.5)

    # ── helpers ──
    @staticmethod
    def _summary_avg(summary: dict) -> dict[str, float]:
        total = max(1, summary["total"])
        return {k: round(v / total, 2) for k, v in summary.get("score_sums", {}).items()}

    def _record_results(self, loop_id: str, gen_results: list[dict]) -> None:
        with DBSession(db_engine) as db:
            loop = db.get(AutoEnhanceLoop, loop_id)
            if loop:
                loop.results = {"generations": gen_results}
                db.add(loop)
                db.commit()

    # ── crash / reload recovery ──
    def reconcile_orphans(self) -> None:
        """Mark loops left non-terminal by a restart as failed — can't resume."""
        with DBSession(db_engine) as db:
            stmt = select(AutoEnhanceLoop).where(
                AutoEnhanceLoop.status.in_([RunStatus.pending, RunStatus.preparing, RunStatus.running])
            )
            for loop in db.exec(stmt).all():
                loop.status = RunStatus.failed
                loop.error = "Loop interrupted by an API restart and cannot resume."
                loop.finished_at = _now()
                db.add(loop)
            db.commit()


manager = AutoEnhanceManager()
