# apps/accounts (Django side)

Session auth and identity, ported from `bn7ya/template`. Django auth +
Groups/Permissions is the only authorization system here — no parallel
roles table.

## Files
- `repositories/user_repository.py` — the only place this app touches the
  ORM: `find_by_username`/`find_by_email`, `with_groups` (prefetches
  groups+permissions for `/me/`), `group_names`/`permission_codenames`,
  `create`/`add_to_group`/`grant_to_group`/`deactivate` (users are
  deactivated, never removed).
- `services/account_service.py` — `AccountService(user=None)`: `sign_in`
  (same error message for a bad password and an unknown username, on
  purpose — see `INVALID_CREDENTIALS`), `sign_out`, `identity()` (what
  `/me/` returns), `has_group`.
- `views.py`/`urls.py` — `GET /api/auth/csrf/` (public — issues the cookie a
  not-yet-signed-in SPA needs before its first unsafe request),
  `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/`.
- `serializers.py` — `SignInSerializer` (in), `IdentitySerializer` (out;
  keep in sync with `AccountService.identity()` and, once the Angular auth
  feature is built, `core/auth/data/auth.types.ts`).
- `permissions.py` — `InGroup` (subclass with a `group` name),
  `IsOwnerOrStaff` (object-level, needs `BaseModel.created_by`).
- `management/commands/seed_default_operator.py` — **Mesbah-specific, not
  from the template.** Mesbah is single-user; instead of a signup flow, this
  idempotent command creates exactly one superuser (`MISBAH_ADMIN_USERNAME`/
  `MISBAH_ADMIN_PASSWORD` env, defaulting to a generated password printed
  once) if no user exists yet. Run it once after `migrate` on first boot.

## Gotchas
- A refused sign-in is **403, not 401** — DRF downgrades
  `AuthenticationFailed` to 403 when no authenticator can offer a
  `WWW-Authenticate` challenge, and cookie/session auth has none. The reason
  is in the body (`error.message`), not the status code.
- `User` doesn't inherit `apps.common.models.BaseModel` (it's
  `django.contrib.auth`'s own model) — no `deleted_at`, so
  `UserRepository` does not extend `BaseRepository`.
- The frontend is expected to read `groups` from `/me/` for its route
  guards and to show/hide affordances — that is a convenience only; the
  real security boundary is each view's `permission_classes`.
