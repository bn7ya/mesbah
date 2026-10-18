from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from mesbah.train.contract import ExampleSource

type Role = Literal["system", "user", "assistant"]
type ChatTurn = dict[str, str]

ROLES: tuple[Role, ...] = ("system", "user", "assistant")
PLAIN_LABELS: dict[Role, str] = {"system": "System", "user": "User", "assistant": "Assistant"}


class Tokenizer(Protocol):
    @property
    def eos_token(self) -> str | None: ...

    def apply_chat_template(self, conversation: list[ChatTurn], **kwargs: object) -> object: ...

    def encode(self, text: str, **kwargs: object) -> list[int]: ...


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    thinking: str | None = None


@dataclass(frozen=True)
class Conversation:
    messages: tuple[Message, ...]


@dataclass(frozen=True)
class PlainText:
    text: str


type Row = Conversation | PlainText


@dataclass(frozen=True)
class Rows:
    rows: tuple[Row, ...]
    skipped: int


@dataclass(frozen=True)
class Pair:
    prompt: str
    completion: str


@dataclass(frozen=True)
class Prepared:
    pairs: tuple[Pair, ...]
    skipped: int
    tokens: int
    first_rejection: str | None = None


def _message(value: object) -> Message | None:
    if not isinstance(value, dict):
        return None
    found: Mapping[str, object] = cast(Mapping[str, object], value)
    role: object = found.get("role")
    content: object = found.get("content")
    thinking: object = found.get("thinking")
    if not isinstance(content, str) or not (thinking is None or isinstance(thinking, str)):
        return None
    for known in ROLES:
        if role == known:
            return Message(role=known, content=content, thinking=thinking or None)
    return None


def parse_row(value: object) -> Row | None:
    if not isinstance(value, dict):
        return None
    found: Mapping[str, object] = cast(Mapping[str, object], value)
    text: object = found.get("text")
    if "messages" not in found:
        return PlainText(text) if isinstance(text, str) and text.strip() else None
    entries: object = found["messages"]
    if not isinstance(entries, list) or not entries:
        return None
    messages: list[Message] = []
    for entry in cast(list[object], entries):
        message: Message | None = _message(entry)
        if message is None:
            return None
        messages.append(message)
    target: Message = messages[-1]
    if target.role != "assistant" or not (target.content.strip() or target.thinking):
        return None
    return Conversation(tuple(messages))


def load_rows(sources: Sequence[ExampleSource]) -> Rows:
    rows: list[Row] = []
    skipped: int = 0
    for source in sources:
        taken: int = 0
        with Path(source.path).open("rb") as stream:
            for raw in stream:
                if source.max_rows is not None and taken >= source.max_rows:
                    break
                try:
                    line: str = raw.decode("utf-8")
                except UnicodeDecodeError:
                    skipped += 1
                    continue
                if not line.strip():
                    continue
                try:
                    parsed: object = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                row: Row | None = parse_row(parsed)
                if row is None:
                    skipped += 1
                    continue
                rows.append(row)
                taken += 1
    return Rows(rows=tuple(rows), skipped=skipped)


def _turn(message: Message) -> ChatTurn:
    turn: ChatTurn = {"role": message.role, "content": message.content}
    if message.role == "assistant" and message.thinking:
        turn["reasoning_content"] = message.thinking
    return turn


def _has_template(tokenizer: Tokenizer) -> bool:
    return bool(getattr(tokenizer, "chat_template", None))


def _render(
    tokenizer: Tokenizer, turns: list[ChatTurn], *, generation: bool, thinking: bool
) -> str:
    rendered: object
    try:
        rendered = tokenizer.apply_chat_template(
            turns, tokenize=False, add_generation_prompt=generation, enable_thinking=thinking
        )
    except TypeError:
        rendered = tokenizer.apply_chat_template(
            turns, tokenize=False, add_generation_prompt=generation
        )
    if not isinstance(rendered, str):
        raise TypeError("the chat template did not render text")
    return rendered


def _added_bos(tokenizer: Tokenizer) -> str | None:
    bos: object = getattr(tokenizer, "bos_token", None)
    if not isinstance(bos, str) or not bos:
        return None
    with_special: list[int] = tokenizer.encode("a", add_special_tokens=True)
    without: list[int] = tokenizer.encode("a", add_special_tokens=False)
    return bos if len(with_special) > len(without) else None


def _plain_pair(conversation: Conversation, eos: str) -> Pair:
    *prior, target = conversation.messages
    lines: list[str] = [f"{PLAIN_LABELS[message.role]}: {message.content}" for message in prior]
    prompt: str = "\n".join([*lines, f"{PLAIN_LABELS['assistant']}: "])
    reasoning: str = f"<think>\n{target.thinking}\n</think>\n\n" if target.thinking else ""
    return Pair(prompt=prompt, completion=f"{reasoning}{target.content}{eos}")


def render(conversation: Conversation, tokenizer: Tokenizer, added_bos: str | None) -> Pair | None:
    eos: str = tokenizer.eos_token or ""
    if not _has_template(tokenizer):
        return _plain_pair(conversation, eos)
    *prior, target = conversation.messages
    thinking: bool = bool(target.thinking)
    prompt: str = _render(
        tokenizer, [_turn(message) for message in prior], generation=True, thinking=thinking
    )
    full: str = _render(
        tokenizer,
        [_turn(message) for message in conversation.messages],
        generation=False,
        thinking=thinking,
    )
    if added_bos is not None and prompt.startswith(added_bos) and full.startswith(added_bos):
        prompt, full = prompt[len(added_bos) :], full[len(added_bos) :]
    if not full.startswith(prompt):
        return None
    completion: str = full[len(prompt) :]
    # The template ends a turn with eos and a newline; the model should stop at the eos.
    if eos and completion.rstrip().endswith(eos):
        completion = completion.rstrip()
    return Pair(prompt=prompt, completion=completion) if completion.strip() else None


def prepare(rows: Sequence[Row], tokenizer: Tokenizer) -> Prepared:
    added_bos: str | None = _added_bos(tokenizer)
    pairs: list[Pair] = []
    skipped: int = 0
    tokens: int = 0
    first_rejection: str | None = None
    for row in rows:
        pair: Pair | None
        if isinstance(row, PlainText):
            pair = Pair(prompt="", completion=row.text)
        else:
            try:
                pair = render(row, tokenizer, added_bos)
            except Exception as exc:  # noqa: BLE001 - a template may reject one conversation
                pair = None
                first_rejection = first_rejection or f"{type(exc).__name__}: {exc}"
            if pair is None:
                first_rejection = first_rejection or "the chat template does not extend the prompt"
        if pair is None:
            skipped += 1
            continue
        pairs.append(pair)
        tokens += len(tokenizer.encode(pair.prompt + pair.completion, add_special_tokens=False))
    return Prepared(
        pairs=tuple(pairs), skipped=skipped, tokens=tokens, first_rejection=first_rejection
    )
