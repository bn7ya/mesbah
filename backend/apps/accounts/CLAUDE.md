# apps/accounts

Identity and sessions. The backend half of the auth slice.

## Its counterpart

`frontend/src/app/core/auth/` — **not** `features/auth/`.

This is the documented exception to rule 13's name mirroring. Auth is not a page;
it is the thing every page depends on, so on the frontend it lives in `core/`
where guards and the HTTP interceptor can reach it without importing a feature.
Any *page* built on top of this — a profile screen, a user admin screen — is a
normal slice with a normal mirrored name.

The app is called `accounts` rather than `auth` because `django.contrib.auth`
already owns the `auth` app label. It is still mounted at `/api/auth/`.

## Endpoints

| Method | Path | Auth | Returns |
|---|---|---|---|
| `GET` | `/api/auth/csrf/` | public | `204`, sets the `csrftoken` cookie |
| `POST` | `/api/auth/login/` | public | `200` identity, `403` on refusal |
| `POST` | `/api/auth/logout/` | session | `204` |
| `GET` | `/api/auth/me/` | session | `200` identity |

Identity shape — mirrored by `Identity` in `core/auth/data/auth.types.ts`:

```json
{
  "id": 1, "username": "sara", "email": "sara@example.com",
  "first_name": "", "last_name": "",
  "is_staff": false, "is_superuser": false,
  "groups": ["members"],
  "permissions": ["orders.add_order"]
}
```

No list endpoint here, so rule 17 does not apply.

## Layers

```
views.py  →  services/account_service.py  →  repositories/user_repository.py  →  User / Group
```

`serializers.py` and `permissions.py` sit beside the views. Both are under three
items, so neither is a package yet (rule 19).

There are **no models**. `User`, `Group` and `Permission` come from
`django.contrib.auth`, which is the whole point of rule 20 — there is no roles
table here and there is not going to be one. `migrations/` is empty and stays
empty unless this app grows a model of its own.

## Classes and methods

**`UserRepository`** (`repositories/user_repository.py`) — every read and write of users,
groups and permissions. Finds a user by username or email, loads one with groups and
permissions prefetched, lists group names and permission codenames, creates users with a
hashed password, adds users to groups, grants permissions to groups, and deactivates users
(users are never deleted).

**`AccountService`** (`services/account_service.py`) — the session and the identity, for the
acting user.
- `sign_in()` authenticates and starts a session; an unknown username and a wrong password
  get the same refusal, a deactivated account its own.
- `sign_out()` ends the session, and is safe to call twice.
- `identity()` is what `/api/auth/me/` returns: the user, their group names and permissions.
- `has_group()` — superusers are in every group.

**`InGroup`** / **`IsOwnerOrStaff`** (`permissions.py`) — DRF permissions over Django
groups: membership of a named group (subclass and set `group`), and the row's creator or
staff for object-level checks.

**`CsrfView`**, **`SignInView`**, **`SignOutView`**, **`MeView`** (`views.py`) — the four
endpoints in the table above. Each parses, makes one service call and serialises.

**`SignInSerializer`** / **`IdentitySerializer`** (`serializers.py`) — the sign-in input and
the identity output. Shape only; `IdentitySerializer` mirrors the frontend's `Identity`.

## Decisions worth not re-litigating

**Session cookies, not tokens.** Frontend and backend are same-origin in both
environments — the Angular dev server proxies `/api` in development, nginx does
it in production. Same-origin means `HttpOnly` session cookies work, and an
`HttpOnly` cookie cannot be read by injected script the way a stored JWT can.
The cost is CSRF, which is why `/api/auth/csrf/` exists and why the frontend
interceptor sends `X-CSRFToken`.

**`UserRepository` does not extend `BaseRepository`.** `User` is Django's model,
not ours: no `deleted_at`, so the soft-delete helpers have nothing to act on.
Deactivating is what deleting a user means here — `created_by` points at user
rows from every table in the schema, so removing one would cascade through the
entire audit trail.

**A refused sign-in answers 403, not 401.** DRF downgrades `AuthenticationFailed`
to 403 whenever no authenticator can produce a `WWW-Authenticate` header, and
cookie auth has no challenge scheme to offer. RFC 9110 requires that header on a
401, so 403 is the honest status — the reason travels in the body, where `code`
is still `authentication_failed`. Do not add a custom 401 exception to "fix"
this; the frontend already distinguishes a refused sign-in from a lost session by
URL, in `core/http/error.interceptor.ts`.

**Wrong password and unknown username return the same message.** Distinguishing
them turns the endpoint into an account enumerator. A *deactivated* account gets
its own message, because that user needs to know to contact an administrator and
already proved they know the password.

**`/api/auth/me/` returns permissions as well as groups.** Guards key off group
names; individual affordances sometimes need finer granularity. Both are already
loaded, so returning both costs nothing.

**`with_groups()` prefetches.** `/api/auth/me/` reads groups and permissions on
every call. Without the prefetch it is four queries per request.

## Adding a group

Groups are data, not code. Create them in a data migration that calls
`UserRepository.ensure_group()` and `grant_to_group()` — never by hand in an
environment, or production and development drift apart within a week.
