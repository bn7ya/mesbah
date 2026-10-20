# backend/contracts

What a release promises, as JSON generated from the code: the API schema, the command line,
the shipped migrations, and the files Django exchanges with the trainer and the exporter
(ADR-010). The normal test run compares the code with these files, strictly. None of it ships:
the wheel and the sdist take only `mesbah`, `apps` and `config`.

## The files

| File | Made by | What it pins |
|---|---|---|
| `openapi.json` | `apps/common/tests/test_openapi_contract.py` | the `/api` schema as spectacular writes it, without its version |
| `cli.json` | `mesbah/tests/test_cli_contract.py` | `mesbah`'s commands and flags with their defaults, and Mesbah's own `manage` commands |
| `migrations.json` | `apps/common/tests/test_migration_contract.py` | each app's migrations and the sha256 of each file, without Django's generated line |
| `compat.json` | `apps/serving/tests/test_client_contract.py` | `/v1` and `/ollama` as the official `openai` and `ollama` clients call them, against the fake engine served for real: each call's status, content type and the shape of its body or of each streamed event |
| `files.json` | `mesbah/tests/test_files_contract.py` | the training config of a LoRA and a pretrain run, every kind of `status.json`, the fields of every event, and the export config and status |

## Changing one

A failing contract test prints the diff. When the change is meant:

```bash
pytest --update-contracts       # rewrites every file here from the code
git diff backend/contracts/     # read it
```

Then add a line under `### Contracts` in `CHANGELOG.md`'s `[Unreleased]`, and commit all three
with the code. At release time `tools/release/contracts.py` compares these files with the
previous release's and says whether the change is breaking, additive or neither, so the version
bump can be checked against it.

## Classes and methods

**`Contract`** (`__init__.py`) — `check(name, value)` compares `value`, written as canonical JSON
(sorted keys, two spaces, UTF-8, a final newline, by **`canonical()`**), with the file `name`
here. It fails with the first 80 lines of a unified diff and how to accept the change, or
rewrites the file when `update` is set. The `contract` fixture in `backend/conftest.py` gives a
test one, with `update` from `pytest --update-contracts`; the `contract` marker tags such tests.

**`shape()`** (`shapes.py`) — a JSON value with its values replaced by their types (`string`,
`integer`, `number`, `boolean`, `null`); lists become the distinct shapes of their items, and
the keys clients branch on (`object`, `owned_by`, `finish_reason`, `role`, `done`,
`done_reason`, `code`, `type`) keep their values. **`events()`** — the shapes of a response
body: every distinct server-sent event or NDJSON line in the order they first appear, or the
one JSON document. **`distinct()`** — shapes without repeats, first seen first.

## Decisions worth not re-litigating

**Generated, never written by hand.** A snapshot someone edits is a promise nobody checked. Each
file is whatever its test produces from the code, so a diff here is always a change in the code.

**Strict in the gate, classified at release.** Any difference fails the commit that made it, so
nothing changes unnoticed. Whether that difference is allowed in a release is a separate question,
answered against the previous release.

**A migration's file is pinned, not only its name.** Editing a migration that a release shipped
changes nothing on a database that already ran it, so the two drift apart in silence.
