# Backend memory

Narrows the root `CLAUDE.md` to the Django side. Read `.claude/docs/design-pattern.md` §2 for the layering contract; this file is the map.

## Layout

```
backend/
  manage.py
  pyproject.toml            deps, ruff, mypy, pytest
  entrypoint.sh             wait for Postgres → migrate → exec the command
  config/
    settings/{base,dev,prod}.py   Docker modes
    settings/local.py             `mesbah start` (ADR-003)
    urls.py                 every slice mounted under /api/; the Angular app when Django serves it
    spa.py                  index.html for any path Angular routes
    celery.py               broker config comes from Django settings
  tools/build_wheel.py      builds the frontend into the wheel
  apps/
    common/                 BaseModel, BaseRepository, pagination, errors, health
    accounts/               identity and sessions — /api/auth/
    <feature>/              one app per frontend page (rule 13)
  mesbah/                   code that runs outside Django; never imports apps (ADR-008)
```

A feature app:

```
apps/<feature>/
  models/                   or models.py under ~3 items
  repositories/             the only place .objects. appears
  services/                 business rules, transactions, permission decisions
  views/                    or views.py
  serializers/              or serializers.py
  permissions.py
  urls.py
  migrations/
  tests/
  CLAUDE.md                 required (rule 3)
```

## The flow

```
View  →  Service  →  Repository  →  Model
 │
 └── Serializer (shape only)
```

Each layer calls only the one below it. A view that touches a repository, or a
service that touches `.objects.`, is the pattern broken — not a shortcut.

## What the hook enforces

`.claude/hooks/guard-checks.py` runs after every edit and blocks:

- `.objects.` anywhere under `apps/` outside `repositories/` and `migrations/`
- `.raw(`, `.extra(`, `cursor.execute(`
- `.hard_delete(` and `queryset.delete()`

Tests are not exempt. Setup that needs to create a row goes through the
repository, which is also how the application would do it.

## Conventions

**Services take the acting user** in `__init__`. Permission decisions beyond the
route level are theirs. `AccountService` is the one service allowed a `None`
user, because on the sign-in path there is not one yet.

**Repositories return querysets or instances.** They contain no rules. If a
method name contains a business concept — `submittable_for_review()` — the rule
belongs in the service and the repository should be given the filter instead.

**Every endpoint carries `@extend_schema`.** The Swagger page at
`/api/schema/swagger-ui/` is the contract `angular_engineer` builds against, so
an undocumented endpoint is an unfinished one.

**Errors have one shape** — `{"error": {"code", "message", "fields?"}}`, from
`apps/common/exceptions.py`. `message` is user-facing copy; write it as copy.

**Groups are data.** Provision them in data migrations via
`UserRepository.ensure_group()`, never by hand in an environment.

## Backups

`django-dbs` is the backup solution. One encrypted file per backup, holding two
copies of the data plus Reed-Solomon parity, so bit-rot is repaired on restore
instead of silently restored.

It reads the models directly, so **a backup covers every slice automatically** —
a new feature needs no registration. Register a model in `apps/<feature>/dbs.py`
only to override a default: embed a file a `CharField` points at, or exclude a
cache column.

```python
# apps/orders/dbs.py
from dbs import FieldType, ModelBackup, backup_registry
from apps.orders.models import Invoice

@backup_registry.register(Invoice)
class InvoiceBackup(ModelBackup):
    overrides = {
        "scanned_pdf_path": FieldType.FILE_PATH,   # embed the file at that path
        "render_cache": FieldType.EXCLUDE,         # regenerable, don't store it
    }
```

The `backup` service runs `dbs schedule` on a loop; backups land in the
`backups` volume, which `backend` mounts too so the panel can read them. By hand:

```bash
docker compose exec backend python manage.py dbs backup   backup.dbs
docker compose exec backend python manage.py dbs validate backup.dbs                # structure only
docker compose exec backend python manage.py dbs validate backup.dbs --passphrase   # + decryption
docker compose exec backend python manage.py dbs restore  backup.dbs --dry-run      # changes nothing
docker compose exec backend python manage.py dbs restore  backup.dbs
docker compose exec backend python manage.py dbs health
docker compose exec backend python manage.py dbs upgrade --check                    # after a bump
```

**The panel is `/admin/dbs/`**, superusers only, mounted by the library inside the
admin with no URLconf entry. It sets the schedule, grades backup health, keeps an
audit trail, takes a backup to download or push, and restores one, dry run first.
It lives under `/admin/` because nginx already proxies that prefix.

**The session guard** (`DBSSecurityMiddleware`) scores every superuser request to
the admin and ends a session that looks hijacked. The first superuser to open the
admin is sent once to its setup wizard. If it locks you out:
`python manage.py dbs security unlock <username>`. In production it reads the
client from `X-Forwarded-For`; set `DBS_TRUSTED_PROXIES` to the number of
proxies in front of gunicorn, nginx included.

**The schedule.** `DBS_SCHEDULER = "command"`, so only the `backup` service takes
scheduled backups. Until the schedule is turned on at
`/admin/dbs/backupschedule/`, it runs the plan in settings: every
`DBS_SCHEDULE_INTERVAL`, keeping `DBS_SCHEDULE_KEEP`. The service reads which one
to follow when it starts, so after turning the schedule on run
`docker compose restart backup`; from then on the panel decides.

**`DBS_PASSPHRASE` is the whole thing.** The key is derived from it with Argon2id
and never stored. Lose it and every backup is unreadable — that is the design.
Keep it somewhere that is not the machine being backed up.

**Run one scheduler per output directory.** Two loops sharing a directory race on
retention and delete each other's backups.

**A backup on the same machine is not a backup.** Set `DBS_SSH_HOST` before this
counts as one; every scheduled backup is then pushed offsite, keeping
`DBS_SCHEDULE_KEEP_REMOTE`.

## Classes and methods in `config/`

**`settings/base.py`** — everything every environment shares, Mesbah's data folder and the
built-in engine's address and token (`MESBAH_RUNTIME_URL`, `MESBAH_RUNTIME_TOKEN`) included.
The API schema's version is `mesbah.__version__`, the one place the version is written.
`env()`, `env_bool()` and `env_list()` read the environment with a default.
**`settings/dev.py`** adds the debug toolbar (`show_debug_toolbar()` reads `DEBUG` at request
time) and console email; **`settings/prod.py`** adds the TLS, cookie and SMTP settings behind
nginx.

**`urls.py`** — every API path under `/api/`, one prefix per app, plus the schema views,
the admin (which carries the backup panel at `/admin/dbs/`), and the OpenAI- and
Ollama-compatible APIs at `/v1/` and `/ollama/` (`apps/serving/compat_urls.py`).

**`settings/local.py`** (Mesbah) — `mesbah start`: the database from `DATABASE_URL`, a file
cache and a filesystem broker in the data folder, the built Angular app served by WhiteNoise.
**`spa.py`** — `index()`, index.html for every path that is not the API, the compatible APIs,
the admin or a file.

**`celery.py`** — the Celery app, configured from Django settings under `CELERY_`; tasks go to
the `default` queue, one at a time per worker thread, acknowledged when done — except those that
name the `heavy` queue (training, merging, converting), which one solo worker serves in turn.
**`asgi.py`** — the entry point uvicorn serves (ADR-006), with static files in `DEBUG`.
**`wsgi.py`** — kept for tools that want WSGI; nothing in Mesbah serves it.

## Commands

Dependencies install from `pyproject.toml` with uv (`uv pip install -r pyproject.toml --extra
dev`); `pip install -e` does not work, because the wheel moves `apps` and `config` under
`mesbah/_server` (ADR-003). `python -m mesbah start` runs the pip mode from a checkout;
`python backend/tools/build_wheel.py` builds the frontend and the wheel into `backend/dist/`.

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend pytest
docker compose exec backend ruff check . --fix
docker compose exec backend mypy .                       # strict, rule 30
docker compose exec backend python manage.py spectacular --fail-on-warn --file /dev/null
```

Before handing a slice to the frontend:

```bash
docker compose exec backend python manage.py makemigrations --check --dry-run   # no pending changes
docker compose exec backend pytest
```

## Adding a slice

1. `apps/<feature>/` with the layout above — the name matches the Angular feature directory.
2. Add `"apps.<feature>"` to `LOCAL_APPS` in `config/settings/base.py`.
3. Add `path("<feature>/", include("apps.<feature>.urls"))` to `api_patterns` in `config/urls.py`.
4. Write `apps/<feature>/CLAUDE.md`. The `Stop` hook blocks finishing without it.
