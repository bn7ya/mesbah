from __future__ import annotations

from apps.datasets.services.formats import (
    ColumnMap,
    Sample,
    TrainingRow,
    chosen,
    detect,
    has_thinking,
    normalise,
    sample,
)

type Row = dict[str, object]


def detected(rows: list[Row]) -> ColumnMap:
    columns: list[str] = list(dict.fromkeys(key for row in rows for key in row))
    return detect(columns, rows)


def only(row: Row) -> TrainingRow | None:
    return normalise(row, detected([row]))


def test_messages_are_read_as_they_are() -> None:
    row: Row = {
        "messages": [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "ما عاصمة عمان؟"},
            {"role": "assistant", "content": "مسقط."},
        ]
    }

    assert detected([row]).format == "messages"
    assert only(row) == {
        "messages": [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "ما عاصمة عمان؟"},
            {"role": "assistant", "content": "مسقط."},
        ]
    }


def test_reasoning_inside_a_turn_becomes_its_thinking() -> None:
    row: Row = {
        "messages": [
            {"role": "user", "content": "2+2?"},
            {"role": "assistant", "content": "4", "reasoning_content": "Two and two."},
        ]
    }

    converted: TrainingRow | None = only(row)

    assert converted is not None
    assert converted["messages"][-1] == {
        "role": "assistant",
        "content": "4",
        "thinking": "Two and two.",
    }
    assert has_thinking(converted)


def test_sharegpt_turns_are_renamed() -> None:
    row: Row = {
        "conversations": [
            {"from": "system", "value": "Be kind."},
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello!"},
        ]
    }

    assert detected([row]).format == "sharegpt"
    assert only(row) == {
        "messages": [
            {"role": "system", "content": "Be kind."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
    }


def test_an_unknown_speaker_skips_the_row() -> None:
    row: Row = {"conversations": [{"from": "human", "value": "x"}, {"from": "tool", "value": "y"}]}

    assert normalise(row, ColumnMap(format="sharegpt", conversation="conversations")) is None


def test_instruction_and_input_make_the_prompt() -> None:
    row: Row = {"instruction": "Translate.", "input": "Good morning", "output": "صباح الخير"}

    mapping: ColumnMap = detected([row])

    assert (mapping.format, mapping.prompt, mapping.input, mapping.reply) == (
        "instruction",
        "instruction",
        "input",
        "output",
    )
    assert only(row) == {
        "messages": [
            {"role": "user", "content": "Translate.\n\nGood morning"},
            {"role": "assistant", "content": "صباح الخير"},
        ]
    }


def test_an_instruction_without_input_is_the_whole_prompt() -> None:
    row: Row = {"instruction": "Say hi.", "input": "", "response": "Hi."}

    assert only(row) == {
        "messages": [
            {"role": "user", "content": "Say hi."},
            {"role": "assistant", "content": "Hi."},
        ]
    }


def test_instruction_wins_over_a_text_column() -> None:
    row: Row = {"instruction": "a", "input": "", "output": "b", "text": "### a b"}

    assert detected([row]).format == "instruction"


def test_every_prompt_and_reply_pair_is_recognised() -> None:
    for prompt, reply in (
        ("prompt", "completion"),
        ("prompt", "response"),
        ("question", "answer"),
        ("query", "response"),
    ):
        row: Row = {prompt: "Q", reply: "A"}
        mapping: ColumnMap = detected([row])

        assert (mapping.format, mapping.prompt, mapping.reply) == (
            "prompt_completion",
            prompt,
            reply,
        )
        assert only(row) == {
            "messages": [
                {"role": "user", "content": "Q"},
                {"role": "assistant", "content": "A"},
            ]
        }


def test_conversational_prompt_and_completion_are_joined() -> None:
    row: Row = {
        "prompt": [{"role": "user", "content": "Q"}],
        "completion": [{"role": "assistant", "content": "A"}],
    }

    assert only(row) == {
        "messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]
    }


def test_preference_pairs_are_not_supported() -> None:
    row: Row = {"prompt": "Q", "chosen": "good", "rejected": "bad"}

    assert detected([row]).format == "unsupported"
    assert only(row) is None


def test_plain_text_is_kept_as_text() -> None:
    row: Row = {"text": "Once upon a time."}

    assert detected([row]).format == "text"
    assert only(row) == {"text": "Once upon a time."}
    assert only({"text": "   "}) is None


def test_unknown_columns_are_unsupported() -> None:
    assert detected([{"title": "x", "body": "y"}]).format == "unsupported"


def test_a_thinking_column_goes_to_the_last_reply() -> None:
    row: Row = {"question": "Why?", "answer": "Because.", "reasoning": "Let me see."}

    mapping: ColumnMap = detected([row])

    assert mapping.thinking == "reasoning"
    converted: TrainingRow | None = normalise(row, mapping)
    assert converted is not None
    assert converted["messages"][-1]["thinking"] == "Let me see."


def test_every_thinking_column_name_is_found() -> None:
    for name in ("reasoning", "thinking", "reasoning_content", "think", "cot"):
        assert detected([{"prompt": "Q", "completion": "A", name: "t"}]).thinking == name


def test_inline_thinking_is_split_from_the_reply() -> None:
    row: Row = {"prompt": "Q", "completion": "<think>\nFirst, Q.\n</think>\n\nA."}

    converted: TrainingRow | None = only(row)

    assert converted is not None
    assert converted["messages"][-1] == {
        "role": "assistant",
        "content": "A.",
        "thinking": "First, Q.",
    }


def test_a_conversation_ending_with_the_user_is_trimmed() -> None:
    row: Row = {
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Bye"},
        ]
    }

    converted: TrainingRow | None = only(row)

    assert converted is not None
    assert [turn["role"] for turn in converted["messages"]] == ["user", "assistant"]


def test_a_row_without_a_reply_is_skipped() -> None:
    assert only({"messages": [{"role": "user", "content": "Hi"}]}) is None
    assert only({"prompt": "Q", "completion": ""}) is None
    assert only({"prompt": "Q", "completion": None}) is None


def test_columns_stored_as_json_text_are_read() -> None:
    row: Row = {
        "messages": '[{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]'
    }

    assert detected([row]).format == "messages"
    assert only(row) is not None


def test_names_are_matched_without_case() -> None:
    mapping: ColumnMap = detected([{"Question": "Q", "Answer": "A"}])

    assert (mapping.prompt, mapping.reply) == ("Question", "Answer")


def test_a_system_column_opens_the_conversation() -> None:
    row: Row = {"system": "Be brief.", "prompt": "Q", "response": "A"}

    converted: TrainingRow | None = only(row)

    assert converted is not None
    assert converted["messages"][0] == {"role": "system", "content": "Be brief."}


def test_chosen_columns_override_the_detection() -> None:
    row: Row = {"title": "Q", "body": "A", "notes": "t"}

    mapping: ColumnMap = chosen("title", "body", "notes", detected([row]))

    assert mapping.format == "prompt_completion"
    assert normalise(row, mapping) == {
        "messages": [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A", "thinking": "t"},
        ]
    }


def test_a_sample_counts_what_it_skips() -> None:
    rows: list[Row] = [{"prompt": "Q", "completion": "A"}, {"prompt": "Q", "completion": ""}]

    tried: Sample = sample(rows, detected(rows))

    assert (len(tried.rows), tried.skipped) == (1, 1)
