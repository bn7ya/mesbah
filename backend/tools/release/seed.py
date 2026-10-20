from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.release.client import Client, Json, items, text
from tools.release.stack import Stack

OWNER: str = "owner"
VIEWER: str = "vera"
PASSWORD: str = "upgrade-check-password-7"  # noqa: S105 - a throwaway install's password
ASKED: str = "Before the upgrade"
CORRECTED: str = "Corrected before the upgrade"
THINKING: str = "Kept across the upgrade"
ENGINE_KEY: str = "sealed-before-the-upgrade"
FINISHED: frozenset[str] = frozenset({"completed", "failed", "cancelled"})


def conversations(count: int) -> bytes:
    rows: list[str] = [
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": f"Question {number}?"},
                    {"role": "assistant", "content": f"Answer {number}.", "thinking": "Think."},
                ]
            }
        )
        for number in range(1, count + 1)
    ]
    return ("\n".join(rows) + "\n").encode()


def events(stream: bytes) -> list[tuple[str, Json]]:
    found: list[tuple[str, Json]] = []
    for block in stream.decode().split("\n\n"):
        lines: list[str] = [
            line for line in block.splitlines() if line and not line.startswith(":")
        ]
        name: str = next((line[7:] for line in lines if line.startswith("event: ")), "message")
        data: str = next((line[6:] for line in lines if line.startswith("data: ")), "")
        if not data:
            continue
        parsed: object = json.loads(data)
        if isinstance(parsed, dict):
            found.append((name, parsed))
    return found


def reply(client: Client, conversation: str, content: str) -> Json:
    stream: bytes = client.send(
        "POST",
        f"/api/chat/{conversation}/reply/",
        json.dumps({"content": content}).encode(),
    ).body
    name, data = events(stream)[-1]
    saved: object = data.get("reply")
    if name != "done" or not isinstance(saved, dict):
        raise RuntimeError(f"the reply ended with {name}: {json.dumps(data)[:300]}")
    return saved


def finished(client: Client, run: str) -> Json:
    done: Json = client.until(f"/api/training/{run}/", lambda body: body.get("status") in FINISHED)
    if done.get("status") != "completed":
        raise RuntimeError(f"run {run} ended {done.get('status')}: {done.get('error_code')}")
    return done


def train(client: Client, project: str, dataset: str, starts_from: str | None) -> str:
    run: Json = client.post(
        "/api/training/",
        {
            "project": project,
            "datasets": [{"id": dataset}],
            "starts_from": starts_from,
            "use_corrections": False,
        },
    )
    version: object = finished(client, text(run, "id")).get("version")
    if isinstance(version, dict):
        return text(version, "id")
    if isinstance(version, str):
        return version
    raise RuntimeError(f"run {text(run, 'id')} names no version")


def base_model(client: Client, dataset: str) -> str:
    design: object = items(client.get("/api/architect/presets/"), "presets")[0].get("design")
    draft: Json = client.post(
        "/api/architect/drafts/",
        {"name": "Upgrade base", "design": design, "tokenizer": "e2e/tokenizer", "seq_len": 128},
    )
    started: Json = client.post(
        f"/api/architect/drafts/{text(draft, 'id')}/train/",
        {"name": "Upgrade base", "datasets": [{"id": dataset}]},
    )
    finished(client, text(started, "run"))
    made: Json = next(
        model
        for model in items(client.get("/api/models/"))
        if str(model.get("repo_id")).startswith("local/")
    )
    return text(made, "id")


def seed(stack: Stack) -> Json:
    owner: Client = Client(stack.base_url)
    owner.get("/api/auth/csrf/")
    owner.post(
        "/api/auth/setup/", {"code": stack.setup_code, "username": OWNER, "password": PASSWORD}
    )
    owner.post("/api/members/", {"username": VIEWER, "password": PASSWORD, "role": "viewers"})
    dataset: str = text(
        owner.upload(
            "/api/datasets/upload/", "chat.jsonl", conversations(12), {"name": "Upgrade rows"}
        ),
        "id",
    )
    owner.until(f"/api/datasets/{dataset}/", lambda body: body.get("status") == "ready")
    model: str = base_model(owner, dataset)
    project: Json = owner.post("/api/projects/", {"name": "Upgrade project", "base_model": model})
    first: str = train(owner, text(project, "id"), dataset, None)
    second: str = train(owner, text(project, "id"), dataset, first)
    conversation: str = text(owner.post("/api/chat/", {"project": text(project, "id")}), "id")
    answered: Json = reply(owner, conversation, ASKED)
    owner.patch(
        f"/api/chat/messages/{text(answered, 'id')}/",
        {"content": CORRECTED, "thinking": THINKING, "seen": text(answered, "updated_at")},
    )
    export: Json = owner.post(f"/api/versions/{first}/exports/", {"format": "lora"})
    exported: Json = owner.until(
        f"/api/versions/exports/{text(export, 'id')}/",
        lambda body: body.get("status") in {"ready", "failed"},
    )
    if exported.get("status") != "ready":
        raise RuntimeError(f"the LoRA export failed: {exported.get('error_code')}")
    engine: Json = owner.post(
        "/api/serving/engines/",
        {
            "name": "Upgrade engine",
            "kind": "openai",
            "base_url": stack.engine_url,
            "api_key": ENGINE_KEY,
            "model_name": "base",
        },
    )
    key: Json = owner.post("/api/serving/keys/", {"name": "upgrade"})
    return {
        "version": stack.version,
        "owner": OWNER,
        "viewer": VIEWER,
        "password": PASSWORD,
        "dataset": dataset,
        "model": model,
        "project": text(project, "id"),
        "slug": text(project, "slug"),
        "versions": [first, second],
        "conversation": conversation,
        "reply": text(answered, "id"),
        "export": text(export, "id"),
        "engine": text(engine, "id"),
        "api_key": text(key, "key"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.seed")
    parser.add_argument("--stack", type=Path, required=True, help="the stack's folder")
    parser.add_argument("--state", type=Path, required=True, help="where to write what it made")
    arguments: argparse.Namespace = parser.parse_args(argv)
    state: Json = seed(Stack.read(arguments.stack))
    arguments.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Seeded Mesbah {state['version']}: {len(state)} things to check after the upgrade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
