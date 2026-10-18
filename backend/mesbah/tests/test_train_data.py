from __future__ import annotations

import json
from pathlib import Path

from mesbah.train.contract import ExampleSource
from mesbah.train.data import (
    Conversation,
    Message,
    Pair,
    PlainText,
    Prepared,
    Rows,
    load_rows,
    parse_row,
    prepare,
)

CHAT: str = json.dumps(
    {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
)


class TemplateTokenizer:
    eos_token: str = "<eos>"
    chat_template: str | None = "template"

    def __init__(self, prompt_suffix: str = "") -> None:
        self.prompt_suffix: str = prompt_suffix

    def apply_chat_template(self, conversation: list[dict[str, str]], **kwargs: object) -> object:
        text: str = "".join(f"<{turn['role']}>{turn['content']}<eos>" for turn in conversation)
        if kwargs.get("add_generation_prompt"):
            return f"{text}<assistant>{self.prompt_suffix}"
        return text

    def encode(self, text: str, **kwargs: object) -> list[int]:
        return [ord(character) for character in text]


class PlainTokenizer(TemplateTokenizer):
    chat_template: str | None = None


def write_lines(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_malformed_lines_are_skipped_and_counted(tmp_path: Path) -> None:
    path: Path = write_lines(
        tmp_path / "rows.jsonl",
        [
            CHAT,
            "",
            "{broken",
            json.dumps(["not", "an", "object"]),
            json.dumps({"messages": [{"role": "user", "content": "no answer"}]}),
            json.dumps({"messages": [{"role": "robot", "content": "x"}, {"role": "assistant"}]}),
            json.dumps({"text": "   "}),
            json.dumps({"text": "a paragraph"}),
        ],
    )

    rows: Rows = load_rows([ExampleSource(path=str(path))])

    assert rows.skipped == 5
    assert rows.rows == (
        Conversation((Message("user", "hi"), Message("assistant", "hello"))),
        PlainText("a paragraph"),
    )


def test_max_rows_caps_each_file(tmp_path: Path) -> None:
    first: Path = write_lines(tmp_path / "first.jsonl", [CHAT] * 5)
    second: Path = write_lines(tmp_path / "second.jsonl", [CHAT] * 3)

    rows: Rows = load_rows(
        [ExampleSource(path=str(first), max_rows=2), ExampleSource(path=str(second))]
    )

    assert len(rows.rows) == 5


def test_a_line_that_is_not_utf8_is_skipped(tmp_path: Path) -> None:
    path: Path = tmp_path / "rows.jsonl"
    path.write_bytes(CHAT.encode() + b"\n\xff\xfe\n")

    rows: Rows = load_rows([ExampleSource(path=str(path))])

    assert (len(rows.rows), rows.skipped) == (1, 1)


def test_the_thinking_of_a_message_is_kept() -> None:
    row: object = json.loads(
        '{"messages": [{"role": "user", "content": "q"},'
        ' {"role": "assistant", "content": "a", "thinking": "because"}]}'
    )
    assert parse_row(row) == Conversation(
        (Message("user", "q"), Message("assistant", "a", thinking="because"))
    )


def test_a_template_that_does_not_extend_the_prompt_is_skipped() -> None:
    rows: tuple[Conversation, ...] = (
        Conversation((Message("user", "hi"), Message("assistant", "hello"))),
    )

    prepared: Prepared = prepare(rows, TemplateTokenizer(prompt_suffix="<think>"))

    assert prepared.pairs == ()
    assert prepared.skipped == 1
    assert prepared.first_rejection is not None


def test_a_template_that_extends_the_prompt_gives_the_remainder_as_completion() -> None:
    rows: tuple[Conversation, ...] = (
        Conversation((Message("user", "hi"), Message("assistant", "hello"))),
    )

    prepared: Prepared = prepare(rows, TemplateTokenizer())

    assert prepared.pairs == (Pair(prompt="<user>hi<eos><assistant>", completion="hello<eos>"),)
    assert prepared.tokens == len("<user>hi<eos><assistant>hello<eos>")


def test_without_a_template_the_turns_are_written_out() -> None:
    rows: tuple[Conversation, ...] = (
        Conversation(
            (
                Message("system", "be brief"),
                Message("user", "2 + 3?"),
                Message("assistant", "5", thinking="two plus three"),
            )
        ),
    )

    prepared: Prepared = prepare(rows, PlainTokenizer())

    assert prepared.pairs == (
        Pair(
            prompt="System: be brief\nUser: 2 + 3?\nAssistant: ",
            completion="<think>\ntwo plus three\n</think>\n\n5<eos>",
        ),
    )


def test_plain_text_is_all_completion() -> None:
    prepared: Prepared = prepare((PlainText("a paragraph"),), TemplateTokenizer())

    assert prepared.pairs == (Pair(prompt="", completion="a paragraph"),)
