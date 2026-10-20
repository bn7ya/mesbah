from __future__ import annotations

import pytest

from mesbah.think import Piece, ThinkingStream, ends_inside, join_thinking, split_thinking

SAMPLES: tuple[tuple[str, bool], ...] = (
    ("<think>\nLet me count: 1, 2.\n</think>\n\nThe answer is 3.", False),
    ("<think>\nافكر في السؤال\n</think>\n\nالجواب ثلاثة.", False),
    ("No tags here, just an answer.", False),
    ("<think>a thought cut short", False),
    ("Before <think>inner</think> after", False),
    ("<think></think>\n\nOnly an answer.", False),
    ("\nthe template opened it\n</think>\n\nanswer", True),
    ("thinking that never closes", True),
)


def streamed(chunks: list[str], *, starts_inside: bool = False) -> tuple[str, str]:
    stream: ThinkingStream = ThinkingStream(starts_inside=starts_inside)
    pieces: list[Piece] = [piece for chunk in chunks for piece in stream.feed(chunk)]
    pieces += stream.close()
    thinking: str = "".join(text for kind, text in pieces if kind == "thinking")
    answer: str = "".join(text for kind, text in pieces if kind == "content")
    return thinking, answer


def test_a_closed_block_is_the_thinking_and_the_rest_the_answer() -> None:
    assert split_thinking("<think>\nstep one\n</think>\n\nDone.") == ("step one", "Done.")


def test_a_block_that_never_closes_is_all_thinking() -> None:
    assert split_thinking("<think>still going") == ("still going", "")


def test_text_without_tags_is_all_answer() -> None:
    assert split_thinking("  Just this.\n") == ("", "Just this.")


def test_a_close_without_an_open_means_the_template_opened_it() -> None:
    assert split_thinking("reasoning\n</think>\n\nanswer") == ("reasoning", "answer")


def test_starts_inside_reads_unclosed_text_as_thinking() -> None:
    assert split_thinking("reasoning only", starts_inside=True) == ("reasoning only", "")


def test_join_and_split_are_inverse() -> None:
    joined: str = join_thinking("step one\nstep two", "Done.")

    assert joined == "<think>\nstep one\nstep two\n</think>\n\nDone."
    assert split_thinking(joined) == ("step one\nstep two", "Done.")


def test_no_thinking_joins_to_the_answer_alone() -> None:
    assert join_thinking("", "Done.") == "Done."


def test_a_prompt_that_ends_in_an_open_block_is_inside() -> None:
    assert ends_inside("<|im_start|>assistant\n<think>\n")
    assert not ends_inside("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert not ends_inside("<|im_start|>assistant\n")


@pytest.mark.parametrize(("text", "starts_inside"), SAMPLES)
def test_the_stream_agrees_with_split_at_every_boundary(text: str, starts_inside: bool) -> None:
    expected: tuple[str, str] = split_thinking(text, starts_inside=starts_inside)

    for at in range(len(text) + 1):
        assert streamed([text[:at], text[at:]], starts_inside=starts_inside) == expected, at
    assert streamed(list(text), starts_inside=starts_inside) == expected


def test_the_stream_names_each_piece_in_order() -> None:
    stream: ThinkingStream = ThinkingStream()

    pieces: list[Piece] = stream.feed("<think>plan</think>\n\nreply") + stream.close()

    assert pieces == [("thinking", "plan"), ("content", "reply")]


def test_a_possible_tag_is_held_until_it_is_known() -> None:
    stream: ThinkingStream = ThinkingStream()

    assert stream.feed("Hello <thi") == [("content", "Hello")]
    assert stream.feed("nk>idea") == [("thinking", "idea")]


def test_closing_flushes_a_partial_tag_as_content() -> None:
    stream: ThinkingStream = ThinkingStream()

    assert stream.feed("Hello <thi") == [("content", "Hello")]
    assert stream.close() == [("content", " <thi")]


def test_a_template_opened_block_streams_as_thinking() -> None:
    stream: ThinkingStream = ThinkingStream(starts_inside=True)

    assert stream.feed("weighing it</thi") == [("thinking", "weighing it")]
    assert stream.feed("nk>\n\nanswer") == [("content", "answer")]
