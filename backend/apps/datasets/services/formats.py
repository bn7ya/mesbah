from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import NotRequired, TypedDict

from mesbah.think import split_thinking

MESSAGES: str = "messages"
SHAREGPT: str = "sharegpt"
INSTRUCTION: str = "instruction"
PROMPT_COMPLETION: str = "prompt_completion"
TEXT: str = "text"
UNSUPPORTED: str = "unsupported"
FORMATS: tuple[str, ...] = (MESSAGES, SHAREGPT, INSTRUCTION, PROMPT_COMPLETION, TEXT)
MESSAGE_ROLES: tuple[str, ...] = ("system", "user", "assistant")

CONVERSATION_COLUMNS: tuple[str, ...] = (
    "messages",
    "conversations",
    "conversation",
    "chat",
    "dialog",
    "dialogue",
)
THINKING_COLUMNS: tuple[str, ...] = ("reasoning", "thinking", "reasoning_content", "think", "cot")
SYSTEM_COLUMNS: tuple[str, ...] = ("system", "system_prompt")
INSTRUCTION_REPLIES: tuple[str, ...] = ("output", "response")
PAIRS: tuple[tuple[str, str], ...] = (
    ("prompt", "completion"),
    ("prompt", "response"),
    ("question", "answer"),
    ("query", "response"),
)
TURN_THINKING_KEYS: tuple[str, ...] = ("thinking", "reasoning_content", "reasoning")
ROLES: dict[str, str] = {
    "system": "system",
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "gpt": "assistant",
    "model": "assistant",
    "bot": "assistant",
    "chatgpt": "assistant",
}

type RawRow = Mapping[str, object]


class Turn(TypedDict):
    role: str
    content: str
    thinking: NotRequired[str]


class TrainingRow(TypedDict, total=False):
    messages: list[Turn]
    text: str


@dataclass(frozen=True)
class ColumnMap:
    format: str
    conversation: str = ""
    system: str = ""
    prompt: str = ""
    input: str = ""
    reply: str = ""
    thinking: str = ""
    text: str = ""

    def required(self) -> list[str]:
        if self.format in (MESSAGES, SHAREGPT):
            return [self.conversation]
        if self.format in (INSTRUCTION, PROMPT_COMPLETION):
            return [self.prompt, self.reply]
        if self.format == TEXT:
            return [self.text]
        return []

    def columns(self) -> list[str]:
        named: list[str] = [self.system, self.input, self.thinking, *self.required()]
        return [column for column in named if column]


@dataclass(frozen=True)
class Sample:
    rows: list[TrainingRow]
    skipped: int


def column_map(fields: Mapping[str, object]) -> ColumnMap:
    known: set[str] = set(ColumnMap.__dataclass_fields__)
    return ColumnMap(**{key: str(value) for key, value in fields.items() if key in known})


def decoded(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("[", "{")):
        try:
            parsed: object = json.loads(value)
        except json.JSONDecodeError:
            return value
        return parsed
    return value


def detect(columns: list[str], sample: Sequence[RawRow]) -> ColumnMap:
    names: dict[str, str] = {column.lower(): column for column in columns}
    thinking: str = _first(names, THINKING_COLUMNS)
    system: str = _first(names, SYSTEM_COLUMNS)
    for wanted in CONVERSATION_COLUMNS:
        if wanted in names:
            style: str | None = _turn_style(names[wanted], sample)
            if style is not None:
                return ColumnMap(
                    format=style, conversation=names[wanted], system=system, thinking=thinking
                )
    reply: str = _first(names, INSTRUCTION_REPLIES)
    if "instruction" in names and reply:
        return ColumnMap(
            format=INSTRUCTION,
            prompt=names["instruction"],
            input=names.get("input", ""),
            reply=reply,
            system=system,
            thinking=thinking,
        )
    for prompt, answer in PAIRS:
        if prompt in names and answer in names:
            return ColumnMap(
                format=PROMPT_COMPLETION,
                prompt=names[prompt],
                reply=names[answer],
                system=system,
                thinking=thinking,
            )
    if TEXT in names:
        return ColumnMap(format=TEXT, text=names[TEXT])
    return ColumnMap(format=UNSUPPORTED)


def chosen(prompt: str, reply: str, thinking: str, detected: ColumnMap) -> ColumnMap:
    return ColumnMap(
        format=PROMPT_COMPLETION,
        prompt=prompt,
        reply=reply,
        thinking=thinking,
        system=detected.system,
    )


def normalise(row: RawRow, mapping: ColumnMap) -> TrainingRow | None:
    if mapping.format == TEXT:
        text: str | None = _text(row.get(mapping.text))
        return {"text": text} if text and text.strip() else None
    turns: list[Turn] | None
    if mapping.format in (MESSAGES, SHAREGPT):
        turns = _turns(decoded(row.get(mapping.conversation)))
    elif mapping.format == INSTRUCTION:
        turns = _instruction(row, mapping)
    elif mapping.format == PROMPT_COMPLETION:
        turns = _pair(row, mapping)
    else:
        return None
    if turns is None:
        return None
    system: str | None = _text(row.get(mapping.system)) if mapping.system else ""
    if system and system.strip() and not any(turn["role"] == "system" for turn in turns):
        turns.insert(0, {"role": "system", "content": system})
    thinking: str | None = _text(row.get(mapping.thinking)) if mapping.thinking else ""
    return _finished(turns, thinking or "")


def sample(rows: Iterable[RawRow], mapping: ColumnMap) -> Sample:
    normalised: list[TrainingRow] = []
    skipped: int = 0
    for row in rows:
        converted: TrainingRow | None = normalise(row, mapping)
        if converted is None:
            skipped += 1
        else:
            normalised.append(converted)
    return Sample(rows=normalised, skipped=skipped)


def has_thinking(row: TrainingRow) -> bool:
    return any("thinking" in turn for turn in row.get("messages", []))


def _first(names: dict[str, str], wanted: tuple[str, ...]) -> str:
    return next((names[name] for name in wanted if name in names), "")


def _turn_style(column: str, rows: Sequence[RawRow]) -> str | None:
    for row in rows:
        value: object = decoded(row.get(column))
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                if "role" in item and "content" in item:
                    return MESSAGES
                if "from" in item and "value" in item:
                    return SHAREGPT
                return None
    if not rows:
        return SHAREGPT if column.lower() == "conversations" else MESSAGES
    return None


def _text(value: object) -> str | None:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list) and all(isinstance(part, dict) for part in value):
        return "".join(str(part.get("text", "")) for part in value if isinstance(part, dict))
    return None


def _turns(value: object) -> list[Turn] | None:
    if not isinstance(value, list) or not value:
        return None
    turns: list[Turn] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        role: str | None = ROLES.get(str(item.get("role", item.get("from", ""))).lower())
        content: str | None = _text(item.get("content", item.get("value")))
        if role is None or content is None:
            return None
        turn: Turn = {"role": role, "content": content}
        if role == "assistant":
            thinking: str = next(
                (str(item[key]) for key in TURN_THINKING_KEYS if item.get(key)),
                "",
            )
            if thinking.strip():
                turn["thinking"] = thinking.strip()
        turns.append(turn)
    return turns


def _side(value: object, role: str) -> list[Turn] | None:
    value = decoded(value)
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return _turns(value)
    text: str | None = _text(value)
    return None if text is None else [{"role": role, "content": text}]


def _instruction(row: RawRow, mapping: ColumnMap) -> list[Turn] | None:
    instruction: str | None = _text(row.get(mapping.prompt))
    extra: str | None = _text(row.get(mapping.input)) if mapping.input else ""
    reply: str | None = _text(row.get(mapping.reply))
    if instruction is None or extra is None or reply is None:
        return None
    prompt: str = f"{instruction}\n\n{extra}" if extra.strip() else instruction
    return [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}]


def _pair(row: RawRow, mapping: ColumnMap) -> list[Turn] | None:
    prompt: list[Turn] | None = _side(row.get(mapping.prompt), "user")
    reply: list[Turn] | None = _side(row.get(mapping.reply), "assistant")
    if prompt is None or reply is None:
        return None
    return [*prompt, *reply]


def _finished(turns: list[Turn], thinking: str) -> TrainingRow | None:
    while turns and turns[-1]["role"] != "assistant":
        turns.pop()
    if not turns or not any(turn["role"] == "user" for turn in turns):
        return None
    for turn in turns:
        if turn["role"] == "assistant" and "thinking" not in turn:
            found: str
            found, turn["content"] = split_thinking(turn["content"])
            if found:
                turn["thinking"] = found
        if turn["role"] != "system" and not turn["content"].strip():
            return None
    last: Turn = turns[-1]
    if thinking.strip() and "thinking" not in last:
        last["thinking"] = thinking.strip()
    return {"messages": turns}
