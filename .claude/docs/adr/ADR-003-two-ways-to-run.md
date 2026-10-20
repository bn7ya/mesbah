# ADR-003: Mesbah runs from `pip install` or from Docker, on one codebase

**Status:** accepted — 2026-10-18 (#8)

## Context

The Template runs only under Docker Compose: Postgres, Redis, a worker, beat, a backup loop,
gunicorn and nginx. Mesbah is also a personal tool: someone with a GPU workstation should get
it with `pip install mesbah` and one command, on Linux, macOS or Windows, without Docker. A
team installs it on a server with Docker. Both must be the same application.

## Decision

- **The backend is the `mesbah` distribution.** `backend/pyproject.toml` is built by hatchling.
  The wheel holds the `mesbah` package; the Django tree goes inside it as `mesbah/_server/apps`
  and `mesbah/_server/config` (hatch `sources`), so generic top-level names never land in
  site-packages. The built Angular app goes in as `mesbah/_spa` (an `artifacts` entry, built by
  `backend/tools/build_wheel.py` and never committed). `mesbah.server` finds the Django tree
  bundled or, in a checkout, beside the package.
- **`mesbah start` brings everything up on one machine:** an embedded PostgreSQL 18 with pgvector
  (`pixeltable-pgserver`, wheels for every platform) in the data folder, migrations and static
  files, uvicorn serving Django and the Angular app, and a Celery worker. No Redis: the broker
  is kombu's filesystem transport and the cache is file-based, both in the data folder.
  `--database-url` uses an existing PostgreSQL instead. Ctrl+C or SIGTERM stops all of it.
- **Docker keeps the Template's shape**, with uvicorn in place of gunicorn (ADR-006) and a
  `mesbah-data` volume mounted at `/data` in every container that touches model files.
- **Settings:** `config/settings/local.py` is the pip mode (`DATABASE_URL`, file cache,
  filesystem broker, the SPA served by WhiteNoise plus `config/spa.py`'s fallback to
  `index.html`); `dev.py` and `prod.py` stay the Docker modes.
- **Dependencies install without building the package** in Docker and CI
  (`uv pip install -r pyproject.toml`), because hatch's path rewrite rules out editable installs
  and a code change should not rebuild the dependency layer.
- **Cancelling work is a database flag** a task checks, never a Celery broadcast, so it behaves
  the same on both brokers.

## Consequences

- The launcher (`mesbah/launcher.py`) owns process supervision in pip mode; Compose owns it in
  Docker. A new long-running process means an entry in both.
- `python -m mesbah` from `backend/` runs the CLI in a checkout; `pip install -e` does not work.
- The embedded Postgres refuses to run as root and switches to its own system user, so the data
  folder must be reachable by that user when Mesbah is started as root.
