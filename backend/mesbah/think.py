from __future__ import annotations

from typing import Literal

type Kind = Literal["thinking", "content"]
type Piece = tuple[Kind, str]
type Phase = Literal["before", "thinking", "after"]

OPEN: str = "<think>"
CLOSE: str = "</think>"


def split_thinking(text: str, *, starts_inside: bool = False) -> tuple[str, str]:
    if starts_inside:
        text = OPEN + text
    opened: int = text.find(OPEN)
    closed: int = text.find(CLOSE)
    if opened != -1 and (closed == -1 or opened < closed):
        inner: int = opened + len(OPEN)
        closed = text.find(CLOSE, inner)
        if closed == -1:
            return text[inner:].strip(), text[:opened].strip()
        return text[inner:closed].strip(), (text[:opened] + text[closed + len(CLOSE) :]).strip()
    if closed != -1:
        return text[:closed].strip(), text[closed + len(CLOSE) :].strip()
    return "", text.strip()


def join_thinking(thinking: str, answer: str) -> str:
    if not thinking.strip():
        return answer
    return f"{OPEN}\n{thinking}\n{CLOSE}\n\n{answer}"


def ends_inside(prompt: str) -> bool:
    return prompt.rfind(OPEN) > prompt.rfind(CLOSE)


def _partial_tag(text: str, tags: tuple[str, ...]) -> int:
    longest: int = 0
    for tag in tags:
        for size in range(min(len(text), len(tag) - 1), longest, -1):
            if text.endswith(tag[:size]):
                longest = size
                break
    return longest


class ThinkingStream:
    def __init__(self, *, starts_inside: bool = False) -> None:
        self._phase: Phase = "thinking" if starts_inside else "before"
        self._buffer: str = ""
        self._started: set[Kind] = set()
        self._held: dict[Kind, str] = {"thinking": "", "content": ""}

    def feed(self, chunk: str) -> list[Piece]:
        self._buffer += chunk
        pieces: list[Piece] = []
        while self._buffer:
            if self._phase == "after":
                self._emit(pieces, "content", self._buffer)
                self._buffer = ""
            elif not self._advance(pieces):
                break
        return pieces

    def close(self) -> list[Piece]:
        pieces: list[Piece] = []
        self._emit(pieces, "thinking" if self._phase == "thinking" else "content", self._buffer)
        self._buffer = ""
        return pieces

    def _advance(self, pieces: list[Piece]) -> bool:
        kind: Kind = "thinking" if self._phase == "thinking" else "content"
        tags: tuple[str, ...] = (CLOSE,) if self._phase == "thinking" else (OPEN, CLOSE)
        positions: list[tuple[int, str]] = [(self._buffer.find(tag), tag) for tag in tags]
        found: list[tuple[int, str]] = [(at, tag) for at, tag in positions if at != -1]
        if not found:
            ready: int = len(self._buffer) - _partial_tag(self._buffer, tags)
            self._emit(pieces, kind, self._buffer[:ready])
            self._buffer = self._buffer[ready:]
            return False
        at, tag = min(found)
        self._emit(pieces, kind, self._buffer[:at])
        self._buffer = self._buffer[at + len(tag) :]
        self._phase = "thinking" if tag == OPEN else "after"
        return True

    def _emit(self, pieces: list[Piece], kind: Kind, text: str) -> None:
        if kind not in self._started:
            text = text.lstrip()
            if not text:
                return
            self._started.add(kind)
        pending: str = self._held[kind] + text
        shown: str = pending.rstrip()
        self._held[kind] = pending[len(shown) :]
        if not shown:
            return
        if pieces and pieces[-1][0] == kind:
            pieces[-1] = (kind, pieces[-1][1] + shown)
        else:
            pieces.append((kind, shown))
