from __future__ import annotations

import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
import uvicorn

from mesbah.runtime import __main__ as entry
from mesbah.runtime.app import create_app
from mesbah.runtime.fake import FakeEngine

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient


def client_for(app: Starlette) -> TestClient:
    # Starlette's TestClient imports httpx; Mesbah ships its successor under another name.
    if importlib.util.find_spec("httpx") is None:
        httpx2.alias_httpx()
    from starlette.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with client_for(create_app(FakeEngine(delay=0), None)) as test_client:
        yield test_client


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path]:
    base: Path = tmp_path / "base"
    base.mkdir()
    adapter: Path = tmp_path / "v1"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}")
    return base, adapter


def load(client: TestClient, base: Path, adapter: Path) -> httpx2.Response:
    body: dict[str, object] = {
        "base": str(base),
        "adapters": [{"name": "v1", "path": str(adapter)}],
    }
    response: httpx2.Response = client.post("/admin/load", json=body)
    return response


def stream(client: TestClient, model: str, content: str, **options: object) -> list[Any]:
    body: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": True,
        **options,
    }
    with client.stream("POST", "/v1/chat/completions", json=body) as response:
        assert response.status_code == 200
        lines: list[str] = [line for line in response.iter_lines() if line]
    payloads: list[str] = [line.removeprefix("data: ") for line in lines]
    return [payload if payload == "[DONE]" else json.loads(payload) for payload in payloads]


def joined(events: list[Any], key: str) -> str:
    return "".join(
        event["choices"][0]["delta"].get(key, "")
        for event in events
        if isinstance(event, dict) and event.get("choices")
    )


def test_it_loads_only_what_is_on_disk(client: TestClient, folders: tuple[Path, Path]) -> None:
    base, adapter = folders

    missing: httpx2.Response = load(client, base / "nowhere", adapter)
    loaded: httpx2.Response = load(client, base, adapter)

    assert missing.status_code == 500
    assert missing.json()["error"]["code"] == "load_failed"
    assert loaded.json()["adapters"] == [{"name": "v1", "path": str(adapter)}]
    assert [card["id"] for card in client.get("/v1/models").json()["data"]] == ["base", "v1"]


def test_it_answers_who_answered_with_its_thinking_apart(
    client: TestClient, folders: tuple[Path, Path]
) -> None:
    load(client, *folders)

    events: list[Any] = stream(client, "v1", "Hello there", stream_options={"include_usage": True})

    assert joined(events, "reasoning_content") == "Thinking about: Hello there"
    assert joined(events, "content") == "Reply from v1: Hello there"
    assert events[-2]["choices"][0]["finish_reason"] == "stop"
    assert events[-2]["usage"]["prompt_tokens"] == 2
    assert events[-1] == "[DONE]"


def test_without_thinking_it_only_answers(client: TestClient, folders: tuple[Path, Path]) -> None:
    load(client, *folders)

    events: list[Any] = stream(
        client, "base", "Hi", chat_template_kwargs={"enable_thinking": False}
    )

    assert joined(events, "reasoning_content") == ""
    assert joined(events, "content") == "Reply from base: Hi"


def test_asked_to_fail_it_breaks_off_with_an_error(
    client: TestClient, folders: tuple[Path, Path]
) -> None:
    load(client, *folders)

    events: list[Any] = stream(client, "v1", "Please [fail]")

    assert events[-2]["error"]["code"] == "generation_failed"
    assert events[-1] == "[DONE]"


def test_asked_for_a_long_reply_it_stops_at_the_limit(
    client: TestClient, folders: tuple[Path, Path]
) -> None:
    load(client, *folders)

    body: dict[str, object] = {
        "model": "v1",
        "messages": [{"role": "user", "content": "[long]"}],
        "max_tokens": 12,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    reply: dict[str, Any] = client.post("/v1/chat/completions", json=body).json()

    assert reply["choices"][0]["finish_reason"] == "length"
    assert reply["usage"]["completion_tokens"] == 12


def test_it_refuses_a_model_it_does_not_hold(
    client: TestClient, folders: tuple[Path, Path]
) -> None:
    body: dict[str, object] = {"model": "v2", "messages": [{"role": "user", "content": "Hi"}]}

    unloaded: httpx2.Response = client.post("/v1/chat/completions", json=body)
    load(client, *folders)
    unknown: httpx2.Response = client.post("/v1/chat/completions", json=body)

    assert unloaded.json()["error"]["code"] == "not_loaded"
    assert unknown.json()["error"]["code"] == "model_not_found"


def test_the_command_serves_the_fake_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    served: dict[str, Any] = {}

    def fake_run(app: Starlette, **options: object) -> None:
        served.update(options, app=app)

    monkeypatch.delenv(entry.TOKEN_VARIABLE, raising=False)
    monkeypatch.setattr(uvicorn, "run", fake_run)

    assert entry.main(["--fake", "--port", "8178"]) == 0
    with client_for(served["app"]) as anonymous:
        assert anonymous.get("/admin/status").json()["loaded"] is False
