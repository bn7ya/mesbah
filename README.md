# مصباح · Mesbah

A studio for customizing language models, for one person or a whole team.

- Pick any model on HuggingFace and chat with it.
- Correct a reply in place, the way you edit a sent message, and correct its thinking
  separately.
- Add HuggingFace datasets and train. Each run adds a **version** that stores only the
  change to the model's weights, so versions are cheap to keep, branch and roll back.
- Run a version on the built-in engine, vLLM, llama.cpp or Ollama, export it to their
  formats, and serve it over OpenAI- and Ollama-compatible APIs.
- Design and pretrain a new model from scratch, MoE or encoder-decoder.
- Every technical detail on screen comes with a plain explanation.

The interface is Arabic first, with English one switch away.

Mesbah is built on [bn7ya/Template](https://github.com/bn7ya/Template). Everything about
how work happens here is in [`CLAUDE.md`](CLAUDE.md) and
[`.claude/docs/design-pattern.md`](.claude/docs/design-pattern.md).

## Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 22 (standalone, signals, zoneless) + Angular Material 22 (Material 3) + Font Awesome 7 Free |
| Backend | Django 5.2 LTS + DRF + drf-spectacular |
| Database | PostgreSQL 18 + pgvector 0.8.6 |
| Cache / broker | Redis 8 |
| Background jobs | Celery 5.6 + django-celery-beat |
| Backups | django-dbs (encrypted, redundant, self-healing) |
| Serving | uvicorn (ASGI) behind nginx; Angular built statically. Or `mesbah start` on one machine |

## Install it

```bash
pip install mesbah
mesbah start
```

`mesbah start` brings up its own PostgreSQL in your user data folder, opens the browser, and
prints a one-time setup code that creates the owner account. Training needs the training parts:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu130   # NVIDIA GPU
pip install "mesbah[train]"
mesbah doctor                                                         # what is missing
```

## Running it with Docker

```bash
cp .env.example .env          # then set DJANGO_SECRET_KEY
docker compose up --watch --build
```

| What | Where |
|---|---|
| Angular | http://localhost:4200 |
| API | http://localhost:4200/api/ |
| Swagger UI | http://localhost:4200/api/schema/swagger-ui/ |
| Django admin | http://localhost:4200/admin/ |

The Angular dev server proxies `/api`, `/admin`, `/static` and `/media` to
Django, so development is same-origin and there is no CORS configuration
anywhere in this project — which is exactly how production behaves behind nginx.

`--watch` gives both sides hot reload: Angular rebuilds on a `src/` change,
Django restarts on a Python change, and a dependency change rebuilds the image.

Chatting with a model and training need the built-in engine and the trainer, which carry torch.
They are the `ml` profile, on the CPU; the GPU overlay puts them on the NVIDIA GPUs (with the
NVIDIA Container Toolkit installed):

```bash
docker compose --profile ml up --watch --build                    # CPU
docker compose -f compose.yaml -f compose.gpu.yaml up --watch --build   # GPU
```

Production:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml -f compose.gpu.yaml up -d --build
```

Angular is built once into a volume; nginx serves it and proxies the API. One
origin, one port.

## Using a version from other tools

Every project is a model on Mesbah's OpenAI- and Ollama-compatible APIs: `support-assistant`
is its active version, `support-assistant:v3` a particular one. Make an API key on the Engines
page, then:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8077/v1", api_key="msb_…")
client.chat.completions.create(model="support-assistant", messages=[{"role": "user", "content": "مرحبا"}])
```

```python
import ollama

client = ollama.Client(host="http://localhost:8077/ollama", headers={"Authorization": "Bearer msb_…"})
client.chat(model="support-assistant", messages=[{"role": "user", "content": "مرحبا"}])
```

A version also exports as a LoRA folder (vLLM, PEFT), merged weights (any engine) or a GGUF file
with a Modelfile (llama.cpp, Ollama), and vLLM, Ollama, llama.cpp or any OpenAI-compatible server
can be connected as the engine that answers in the chat.

## The design pattern

**Vertical Slice + Service/Repository.**

```
frontend/src/app/features/<feature>/     ⟷     backend/apps/<feature>/
```

One Angular feature directory mirrors one Django app mirrors one page.

```
Backend    View  →  Service  →  Repository  →  Model
Frontend   Component  →  Store  →  Api  →  HttpClient
```

Each layer calls only the one below it. `.claude/docs/design-pattern.md` is the
contract and the definition of done.

## What is enforced, and how

Some rules are mechanical, and those are checked rather than reviewed.

| Where | What it blocks |
|---|---|
| `.claude/hooks/guard-checks.py` (`PostToolUse`) | raw px in feature styles, `setTimeout`, native dialogs, `.objects.` outside a repository, raw SQL, hard deletes |
| `.claude/hooks/memory-sync.py` (`Stop`) | finishing a turn with a feature's `CLAUDE.md` missing or stale |
| `.claude/hooks/prompt-log.py` (`UserPromptSubmit`) | nothing — appends every prompt to `prompt.txt` |
| `.claude/hooks/git-flow-gate.py` (`UserPromptSubmit`) | nothing — restates the git flow on any prompt that reads as a feature, fix or refactor |
| `frontend/eslint.config.js` | the same frontend rules, earlier |
| `.github/workflows/ci.yml` | all of the above, plus missing migrations, undocumented endpoints, en/ar key drift, missing feature memory |

Rules that need judgement — vertical slicing, dead code, deprecated APIs, visual
hierarchy — belong to the agents and to review.

## How work is committed

Every feature, fix and refactor opens a GitHub issue before the first edit, and
lands as commits small enough that any one of them can be checked out and run.
The procedure is `.claude/skills/git-flow/SKILL.md`; the rules it enforces are
in [`CLAUDE.md`](CLAUDE.md) under "How work gets committed".

```
issue  →  kind/12-what-it-does  →  gate  →  feat(scope): subject (#12)  →  push  →  PR
```

One issue is one commit is one working application. A request that needs several
issues gets several commits on one branch, and the PR closes them all.

## Backups

`django-dbs` is the backup solution, and the `backup` service runs it on a loop.
Each backup is one encrypted file holding two copies of the data plus
Reed-Solomon parity, so silent corruption is repaired on restore rather than
restored.

It reads the models directly, so a backup covers every slice with nothing to
register per feature. Superusers manage it at `/admin/dbs/`: the schedule,
health, an audit trail, taking a backup and restoring one. Details and the
per-model override hook are in [`backend/CLAUDE.md`](backend/CLAUDE.md).

Two things to get right before it counts as a backup:

- **`DBS_PASSPHRASE`.** The key is derived from it and never stored. Lose it and
  every backup is unreadable. Keep it off the machine being backed up.
- **Offsite.** Set `DBS_SSH_HOST`, and every scheduled backup is also pushed
  there. A backup that only exists on the server it backs up dies with the
  server.

## The agents

`.claude/agents/` holds twelve specialists. `architect` plans a slice and
dispatches the rest; `django_engineer` and `angular_engineer` build the two
halves; `interface_designer`, `copywriter` and `translator` finish it; `cleaner` and
`user_journey_engineer` check it. `db_engineer`, `logic_engineer`, `unifier` and
`mcp_engineer` are pulled in when the work calls for them.

Sessions start in plan mode. See the table in [`CLAUDE.md`](CLAUDE.md).

## What is here already

- `backend/apps/common/` — `BaseModel`, `BaseRepository`, pagination, one error
  envelope, `GET /api/health/`
- `backend/apps/accounts/` — session auth at `/api/auth/`, groups and permissions
- `frontend/src/app/core/` — auth store and guards, i18n with en/ar and RTL,
  CSRF and error interceptors
- `frontend/src/styles/` — the Material theme, the brand palettes and the spacing tokens
- A working sign-in page, in both languages

No feature slices yet. The first one replaces the placeholder redirect in
`app.routes.ts`.

## Prompt log

Every prompt submitted in this project is appended to `prompt.txt` by a hook.
The file is gitignored and stays on the machine that wrote it — a local record
of what was asked, not part of the repository. Do not edit it by hand.
