from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import uvicorn
from starlette.testclient import TestClient

from mesbah.runtime import __main__ as entry
from mesbah.runtime.app import create_app
from mesbah.runtime.engine import Engine, Generation, Placement, placement
from mesbah.runtime.errors import InvalidRequest
from mesbah.runtime.specs import ChatMessage, ChatRequest, LoadSpec

if TYPE_CHECKING:
    from starlette.applications import Starlette
torch: ModuleType = pytest.importorskip("torch")
pytestmark: pytest.MarkDecorator = pytest.mark.ml

MODEL: str = "trl-internal-testing/tiny-Qwen3ForCausalLM"
SEQ2SEQ: str = "hf-internal-testing/tiny-random-t5"
TOKEN: str = "test-token"
GIB: int = 1024**3
PROMPT: list[dict[str, str]] = [{"role": "user", "content": "Say something."}]


def client_for(app: Starlette, token: str | None = TOKEN) -> TestClient:
    headers: dict[str, str] = {"Authorization": f"Bearer {token}"} if token else {}
    return TestClient(app, headers=headers)


def make_adapter(path: Path, seed: int) -> Path:
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM

    torch.manual_seed(seed)
    model: Any = get_peft_model(
        AutoModelForCausalLM.from_pretrained(MODEL), LoraConfig(r=4, target_modules="all-linear")
    )
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if "lora_B" in name:
                parameter.normal_(0.0, 1.0)
    model.save_pretrained(path)
    return path


@pytest.fixture(scope="module")
def adapters(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root: Path = tmp_path_factory.mktemp("adapters")
    return make_adapter(root / "first", 0), make_adapter(root / "second", 1)


@pytest.fixture
def engine() -> Engine:
    return Engine()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with client_for(create_app(engine, TOKEN)) as test_client:
        yield test_client


def load(client: TestClient, **versions: Path) -> dict[str, Any]:
    named: list[dict[str, str]] = [
        {"name": name, "path": str(path)} for name, path in versions.items()
    ]
    response: httpx.Response = client.post("/admin/load", json={"base": MODEL, "adapters": named})
    assert response.status_code == 200, response.text
    status: dict[str, Any] = response.json()
    return status


def ask(client: TestClient, model: str, **options: object) -> httpx.Response:
    body: dict[str, object] = {"model": model, "messages": PROMPT, "max_tokens": 8}
    response: httpx.Response = client.post(
        "/v1/chat/completions", json={**body, "temperature": 0, **options}
    )
    return response


def reply(client: TestClient, model: str, **options: object) -> dict[str, Any]:
    response: httpx.Response = ask(client, model, **options)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def text_of(body: dict[str, Any]) -> str:
    message: dict[str, Any] = body["choices"][0]["message"]
    return f"{message['reasoning_content'] or ''}|{message['content']}"


def stream_events(client: TestClient, model: str) -> list[Any]:
    body: dict[str, object] = {
        "model": model,
        "messages": PROMPT,
        "max_tokens": 8,
        "temperature": 0,
        "stream": True,
    }
    with client.stream("POST", "/v1/chat/completions", json=body) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        lines: list[str] = [line for line in response.iter_lines() if line]
    assert all(line.startswith("data: ") for line in lines)
    payloads: list[str] = [line.removeprefix("data: ") for line in lines]
    return [payload if payload == "[DONE]" else json.loads(payload) for payload in payloads]


def test_health_needs_no_token(engine: Engine) -> None:
    with client_for(create_app(engine, TOKEN), token=None) as anonymous:
        response: httpx.Response = anonymous.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_everything_else_needs_the_token(engine: Engine) -> None:
    app: Starlette = create_app(engine, TOKEN)
    with client_for(app, token=None) as anonymous, client_for(app, token="wrong") as stranger:
        missing: httpx.Response = anonymous.get("/v1/models")
        wrong: httpx.Response = stranger.post("/admin/unload")

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["error"]["code"] == "invalid_api_key"


def test_the_base_and_its_versions_are_the_models(
    client: TestClient, adapters: tuple[Path, Path]
) -> None:
    status: dict[str, Any] = load(client, v1=adapters[0])

    listed: dict[str, Any] = client.get("/v1/models").json()

    assert status["loaded"] is True
    assert status["device"] == "cpu"
    assert status["adapters"] == [{"name": "v1", "path": str(adapters[0])}]
    assert listed["object"] == "list"
    assert [card["id"] for card in listed["data"]] == ["base", "v1"]


def test_a_completion_carries_the_reply_and_its_usage(client: TestClient) -> None:
    load(client)

    body: dict[str, Any] = reply(client, "base")

    choice: dict[str, Any] = body["choices"][0]
    assert body["object"] == "chat.completion"
    assert body["model"] == "base"
    assert choice["message"]["role"] == "assistant"
    assert isinstance(choice["message"]["content"], str)
    assert choice["finish_reason"] in {"stop", "length"}
    assert body["usage"]["prompt_tokens"] > 0
    assert 0 < body["usage"]["completion_tokens"] <= 8
    assert body["usage"]["total_tokens"] == (
        body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]
    )


def test_a_stream_sends_the_role_the_pieces_the_finish_and_done(client: TestClient) -> None:
    load(client)

    events: list[Any] = stream_events(client, "base")

    chunks: list[dict[str, Any]] = events[:-1]
    deltas: list[dict[str, str]] = [chunk["choices"][0]["delta"] for chunk in chunks]
    pieces: list[dict[str, str]] = deltas[1:-1]
    assert events[-1] == "[DONE]"
    assert all(chunk["object"] == "chat.completion.chunk" for chunk in chunks)
    assert deltas[0]["role"] == "assistant"
    assert pieces
    assert all(set(delta) <= {"content", "reasoning_content"} for delta in pieces)
    assert chunks[-1]["choices"][0]["finish_reason"] in {"stop", "length"}
    assert chunks[-1]["usage"]["completion_tokens"] > 0
    thinking: str = "".join(delta.get("reasoning_content", "") for delta in pieces)
    content: str = "".join(delta.get("content", "") for delta in pieces)
    assert f"{thinking}|{content}" == text_of(reply(client, "base"))


def test_a_version_answers_differently_from_the_base_and_the_same_every_time(
    client: TestClient, adapters: tuple[Path, Path]
) -> None:
    load(client, v1=adapters[0])

    base: str = text_of(reply(client, "base"))
    first: str = text_of(reply(client, "v1"))
    again: str = text_of(reply(client, "v1"))

    assert first != base
    assert again == first
    assert text_of(reply(client, "base")) == base


def test_loading_the_same_base_again_adds_and_replaces_versions(
    client: TestClient, adapters: tuple[Path, Path]
) -> None:
    load(client, v1=adapters[0])
    before: str = text_of(reply(client, "v1"))

    load(client, v1=adapters[1])
    replaced: str = text_of(reply(client, "v1"))
    status: dict[str, Any] = load(client, v2=adapters[0])

    assert replaced != before
    assert text_of(reply(client, "v2")) == before
    assert [adapter["name"] for adapter in status["adapters"]] == ["v1", "v2"]
    load(client, v2=adapters[1])
    assert text_of(reply(client, "v2")) == replaced


def test_thinking_switch_and_reasoning_history_reach_the_template(client: TestClient) -> None:
    load(client)
    history: list[dict[str, str]] = [
        *PROMPT,
        {"role": "assistant", "content": "Hello.", "reasoning_content": "A greeting fits."},
    ]
    bare: list[dict[str, str]] = [*PROMPT, {"role": "assistant", "content": "Hello."}]

    def prompt_tokens(**options: object) -> int:
        tokens: int = reply(client, "base", **options)["usage"]["prompt_tokens"]
        return tokens

    assert prompt_tokens(chat_template_kwargs={"enable_thinking": False}) > prompt_tokens(
        chat_template_kwargs={"enable_thinking": True}
    )
    assert prompt_tokens(messages=history) > prompt_tokens(messages=bare)


def test_an_unknown_model_is_not_found(client: TestClient) -> None:
    load(client)

    response: httpx.Response = ask(client, "v9")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
    assert set(response.json()["error"]) == {"message", "type", "code"}


def test_after_unloading_a_completion_is_a_conflict(client: TestClient) -> None:
    load(client)

    status: dict[str, Any] = client.post("/admin/unload").json()
    response: httpx.Response = ask(client, "base")

    assert status["loaded"] is False
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_loaded"


def test_a_malformed_request_is_refused(client: TestClient) -> None:
    load(client)

    no_messages: httpx.Response = client.post("/v1/chat/completions", json={"model": "base"})
    not_json: httpx.Response = client.post("/admin/load", content=b"{")
    bad_role: httpx.Response = ask(client, "base", messages=[{"role": "robot", "content": "x"}])

    for response in (no_messages, not_json, bad_role):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"


def long_request(max_tokens: int) -> ChatRequest:
    return ChatRequest(
        model="base",
        messages=(ChatMessage(role="user", content="Hi"),),
        max_tokens=max_tokens,
        temperature=0,
    )


def test_unloading_interrupts_a_running_generation(engine: Engine) -> None:
    engine.load(LoadSpec(base=MODEL))
    generation: Generation = engine.generate(long_request(2000), threading.Event())
    next(generation)

    unloading: threading.Thread = threading.Thread(target=engine.unload)
    unloading.start()
    list(generation)
    unloading.join()

    assert generation.completion_tokens < 2000
    assert engine.status() == {"loaded": False, "busy": False}


def test_closing_a_generation_midway_frees_the_engine(engine: Engine) -> None:
    engine.load(LoadSpec(base=MODEL))
    request: ChatRequest = long_request(64)
    generation: Generation = engine.generate(request, threading.Event())

    next(generation)
    generation.close()

    assert engine.status()["busy"] is False
    assert "".join(engine.generate(request, threading.Event()))


def test_an_encoder_decoder_model_answers(client: TestClient) -> None:
    loaded: httpx.Response = client.post(
        "/admin/load", json={"base": SEQ2SEQ, "architecture": "seq2seq"}
    )
    torch.manual_seed(0)

    body: dict[str, Any] = reply(client, "base", temperature=1.0)

    assert loaded.json()["architecture"] == "seq2seq"
    assert body["choices"][0]["message"]["content"]


def test_several_gpus_share_the_model_and_one_holds_it_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Properties:
        total_memory: int = 16 * GIB

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda _index: Properties())

    shared: Placement = placement(LoadSpec(base=MODEL, gpu_indices=(0, 1)))
    whole: Placement = placement(LoadSpec(base=MODEL, gpu_indices=(1,)))

    assert (shared.device_map, shared.max_memory) == ("auto", {0: "15GiB", 1: "15GiB"})
    assert shared.precision == torch.bfloat16
    assert shared.device == "cuda:0,1"
    assert (whole.device_map, whole.device) == ({"": 1}, "cuda:1")
    with pytest.raises(InvalidRequest, match="GPU 2"):
        placement(LoadSpec(base=MODEL, gpu_indices=(2,)))


def test_the_command_serves_the_engine_behind_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    served: dict[str, Any] = {}

    def fake_run(app: Starlette, **options: object) -> None:
        served.update(options, app=app)

    monkeypatch.setenv(entry.TOKEN_VARIABLE, TOKEN)
    monkeypatch.setattr(uvicorn, "run", fake_run)

    assert entry.main(["--port", "9100"]) == 0

    assert (served["host"], served["port"]) == ("127.0.0.1", 9100)
    with client_for(served["app"], token=None) as anonymous:
        assert anonymous.get("/admin/status").status_code == 401
    with client_for(served["app"]) as owner:
        status: dict[str, Any] = owner.get("/admin/status").json()
        assert (status["loaded"], status["busy"]) == (False, False)
