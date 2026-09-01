# apps/common (Django side)

Shared foundation every Django app on this side inherits from. Not a page
itself — the one deliberate exception to "one Django app per Angular
feature."

## Files
- `models/base.py` — `BaseModel`: UUID primary key, `created_at`/`updated_at`,
  soft delete (`deleted_at`), `created_by`. Every model in `apps/*` inherits
  this. `objects` (default manager) excludes soft-deleted rows;
  `all_objects` includes them.
- `managers.py` — `SoftDeleteQuerySet`/`SoftDeleteManager`/`AllObjectsManager`
  backing `BaseModel`. `queryset.delete()` marks rows, never removes them;
  `.purge()` (data migrations only) really deletes.
- `repositories/base.py` — `BaseRepository[TModel]`: the only place `.objects`
  may be called outside a `repositories/` module. `active()`/
  `all_including_deleted()`, `get`/`find`/`exists`, `create`/`update`,
  `soft_delete`/`restore`/`bulk_soft_delete`.
- `pagination.py` — `DefaultPagination` (page/page_size, the DRF-wide
  default) and `LargeTablePagination` (cursor-based, for tables where deep
  offsets get expensive — not needed yet at Mesbah's single-user scale).
- `exceptions.py` — `exception_handler`: flattens every DRF error into one
  `{"error": {"code", "message", "fields"?}}` envelope. Wired as
  `REST_FRAMEWORK["EXCEPTION_HANDLER"]`.
- `views.py`/`urls.py` — `GET /api/health/`, the one public (`AllowAny`)
  endpoint: reports whether the process can reach Postgres and Redis.

## Why this exists (relative to the FastAPI side)
This is the Django/DRF half of Mesbah's in-progress backend migration — see
the root plan for the full rewrite (FastAPI+SQLModel+SQLite →
Django+DRF+PostgreSQL+Celery+Redis, ported from the `bn7ya/template`
architecture). `backend/app/` (FastAPI) is untouched and still the one
actually wired into the Angular frontend and the training pipeline; `apps/`
+ `config/` here are the **foundation** of the new backend, brought up and
verified independently (migrations run, schema generates, tests pass)
before any product feature is ported onto it. Do not wire the Angular app
to this yet.

## Deliberately deferred from the template this was ported from
- `django-dbs` (encrypted scheduled backups) is not wired yet — add it once
  there's real data on this side worth backing up.
- Django Channels isn't installed yet; `config/asgi.py` is a plain ASGI app
  for now. Training's live metrics/log-tail WebSocket only gets ported once
  the `training` app itself is ported (a later phase) — that's also when
  Channels + its Redis channel layer get added.
