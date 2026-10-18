# apps/projects

A project is one model being customised: a downloaded base model, the prompt and reply settings
every conversation starts from, and the version everyone chats with. The backend half of the
Projects page.

## Its counterpart

`frontend/src/app/features/projects/` — the Projects page and a project's overview.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/projects/` | viewer | a page of projects, most recently changed first |
| `POST` | `/api/projects/` | trainer | `201` the project, with its base version active; `409 base_model_not_ready` |
| `GET` | `/api/projects/<id>/` | viewer | one project |
| `PATCH` | `/api/projects/<id>/` | trainer | the project; name, description, prompt, thinking, reply settings |
| `DELETE` | `/api/projects/<id>/` | trainer | `204` |

## Layers

```
views.py → services/project_service.py → repositories/project_repository.py → Project
                 └→ apps.versions VersionService.create_root()
```

## Classes and methods

**`Project`** — a name and a slug, a description, the kind (`finetune` now, `scratch` once
models are trained from nothing), the base model (protected while a project uses it), the
active version, the system prompt, whether replies think, and the reply settings
(`temperature`, `top_p`, `max_tokens`).

**`ProjectRepository`** — projects newest-changed first with their base model and active
version, whether a slug is taken (besides one project), and a lookup by slug.

**`ProjectService`**, for the acting user:
- `create()` — refuses a base model that is not downloaded, picks a unique slug, starts thinking
  on when the model supports it, and creates the base version (`VersionService.create_root()`).
- `change()` — a new name gets a new slug; `remove()` soft-deletes.
- `describe()` — one project as the API shows it, its active version by id, number and name.

**`BaseModelNotReady`** (`services/errors.py`) — `409 base_model_not_ready`.

## Decisions worth not re-litigating

**The slug is ASCII.** It names the project in the OpenAI- and Ollama-compatible APIs, where
clients expect plain names; an Arabic name falls back to `project`, numbered when taken.

**A model a project uses can't be removed** (`apps.models` checks `projects`), because every
version of the project is a delta on that model's weights.
