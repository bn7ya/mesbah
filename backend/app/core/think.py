"""Shared helpers for hybrid-reasoning ``<think>…</think>`` blocks.

Thinking models (e.g. Qwen3) emit a think block before the answer. The block
must survive human corrections — training examples that lose it teach the
fine-tuned model to stop thinking — so sessions re-attaches it on edit, while
the auto-enhance loop (which disables thinking on purpose) strips it.
"""
from __future__ import annotations

import re

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def split_think(text: str) -> tuple[str | None, str]:
    """Split ``text`` into ``(thinking, answer)``.

    ``thinking`` is ``None`` when no ``<think>`` block exists (answer model).
    An empty block yields ``""`` — still "a thinking model spoke". A dangling
    unclosed ``<think>`` (truncated output) puts everything after it into
    ``thinking``.
    """
    if not text:
        return None, text
    m = _THINK_RE.search(text)
    if m:
        answer = (text[: m.start()] + text[m.end():]).strip()
        return m.group(1).strip(), answer
    lower = text.lower()
    if "<think>" in lower:  # unclosed (truncated mid-think)
        idx = lower.index("<think>")
        return text[idx + len("<think>"):].strip(), text[:idx].strip()
    return None, text


def join_think(thinking: str, answer: str) -> str:
    """Recombine a thinking chain and an answer in the format models emit."""
    return f"<think>\n{thinking}\n</think>\n\n{answer}"


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
