"""Pure, DB-facing helpers for the auto-enhance loop.

No threads here — the manager owns the orchestration. These build the prompt
message lists, parse the evaluator's JSON, and create the per-generation session.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any, Optional

from sqlmodel import Session, select

from ...core.config import settings
from ...core.models import Message, MessageRole, Project, Task
from ...core.models import Session as ChatSession

SCORE_KEYS = ("logic", "language", "context", "factuality")

# Persona for the responder side of every loop session.
LOOP_ASSISTANT_PERSONA = "أنت مساعد عربي خبير، مفيد ودقيق، تُجيب بعمق ووضوح."

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Remove hybrid-reasoning ``<think>…</think>`` blocks from model output.

    Defensive: even with thinking disabled at the template level, some checkpoints
    still emit a (possibly empty) think block. We never want it in stored training
    data, the transcript, or the JSON the evaluator must return. A dangling unclosed
    ``<think>`` (truncated output) drops everything from it onward.
    """
    if not text:
        return text
    text = _THINK_RE.sub("", text)
    if "<think>" in text:                      # unclosed (truncated mid-think)
        text = text.split("<think>", 1)[0]
    return text.strip()


# ── topic seeding ─────────────────────────────────────────────────────────────
def pick_topic_seed(db: Session, project: Project) -> Optional[Task]:
    """A random Task to anchor the discussion topic, or None to free-generate."""
    tasks = list(db.exec(select(Task).where(Task.project_id == project.id)).all())
    return random.choice(tasks) if tasks else None


def _render_history(history: list[Message]) -> str:
    lines: list[str] = []
    for m in history:
        if m.role == MessageRole.user:
            lines.append(f"مستخدم: {m.content}")
        elif m.role == MessageRole.assistant:
            lines.append(f"مساعد: {m.content}")
    return "\n".join(lines)


def build_ask_messages(
    history: list[Message],
    task_seed: Optional[Task],
    ask_prompt: str,
) -> list[dict[str, str]]:
    """Frame the asker turn. The model outputs ONLY the next question.

    Turn 1 picks a fresh topic (task-seeded when available, else free); later
    turns ask a natural follow-up given the running discussion.
    """
    parts: list[str] = []
    if task_seed:
        topic = task_seed.objective or task_seed.description or task_seed.title
        parts.append(f"الموضوع/الهدف: {task_seed.title}\n{topic}".strip())
    if history:
        parts.append("الحوار حتى الآن:\n" + _render_history(history))
        parts.append("اطرح الآن سؤال المتابعة التالي الذي يعمّق النقاش. أخرِج السؤال فقط.")
    else:
        parts.append("اطرح الآن سؤالك الأول. أخرِج السؤال فقط، دون أي مقدمات.")
    return [
        {"role": "system", "content": ask_prompt},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def build_eval_messages(eval_prompt: str, question: str, answer: str) -> list[dict[str, str]]:
    """Frame the evaluator turn requesting strict JSON scores."""
    user = (
        f"السؤال:\n{question}\n\n"
        f"الإجابة:\n{answer}\n\n"
        "قيّم الإجابة الآن وأعد كائن JSON فقط بالمفاتيح: "
        '{"logic", "language", "context", "factuality"}.'
    )
    return [
        {"role": "system", "content": eval_prompt},
        {"role": "user", "content": user},
    ]


# ── evaluation parsing ────────────────────────────────────────────────────────
def _first_json_object(raw: str) -> Optional[str]:
    """Return the first balanced ``{...}`` substring (brace-count scan)."""
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        c = raw[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return None


def parse_scores(raw: str, scale: int = 10) -> Optional[dict[str, float]]:
    """Robustly extract the four scores. Returns None if unparseable.

    1) first balanced JSON object → json.loads; else 2) regex fallback. Each
    score is coerced to float and clamped to [0, scale]. All four keys required.
    """
    if not raw:
        return None
    raw = strip_think(raw)   # a think block can contain stray braces → strip first

    def _clamp(v: Any) -> Optional[float]:
        try:
            return max(0.0, min(float(scale), float(v)))
        except (TypeError, ValueError):
            return None

    blob = _first_json_object(raw)
    if blob:
        try:
            data = json.loads(blob)
            out = {k: _clamp(data.get(k)) for k in SCORE_KEYS}
            if all(v is not None for v in out.values()):
                return out  # type: ignore[return-value]
        except (json.JSONDecodeError, AttributeError):
            pass

    # Regex fallback — tolerate `"logic": 8`, `logic = 8`, etc.
    found: dict[str, float] = {}
    for key, num in re.findall(
        r'"?(logic|language|context|factuality)"?\s*[:=]\s*(\d+(?:\.\d+)?)', raw, re.I
    ):
        c = _clamp(num)
        if c is not None:
            found[key.lower()] = c
    if all(k in found for k in SCORE_KEYS):
        return {k: found[k] for k in SCORE_KEYS}
    return None


def scores_pass(scores: dict[str, float], thresholds: dict[str, float]) -> bool:
    """True iff every dimension meets or exceeds its threshold."""
    return all(scores.get(k, 0) >= thresholds.get(k, 0) for k in SCORE_KEYS)


def avg_score(scores: dict[str, float]) -> float:
    return round(sum(scores.get(k, 0) for k in SCORE_KEYS) / len(SCORE_KEYS), 2)


# ── session creation ──────────────────────────────────────────────────────────
def create_loop_session(db: Session, project: Project, generation: int) -> ChatSession:
    """A dedicated chat for one generation, bound to the active version."""
    s = ChatSession(
        project_id=project.id,
        title=f"تحسين تلقائي · جيل {generation}",
        system_prompt=LOOP_ASSISTANT_PERSONA,
        model_version_id=project.active_version_id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s
