# apps/common

The foundation every slice inherits from. **Not a feature** — it has no frontend
counterpart and no page, which is why it is the one exception to rule 13.

Nothing here is specific to a domain. If something in this directory only makes
sense for one feature, it is in the wrong place.

## What lives here

| Module | Provides |
|---|---|
| `models/base.py` | `BaseModel` — uuid pk, `created_at`, `updated_at`, `deleted_at`, `created_by` (rule 15) |
| `managers.py` | `SoftDeleteManager`, `AllObjectsManager`, `SoftDeleteQuerySet` (rule 16) |
| `repositories/base.py` | `BaseRepository` — the only sanctioned ORM surface (rule 14) |
| `fields.py` | `MoneyField` — an amount in Omani rials, three decimal places, sent as a string (rule 29) |
| `pagination.py` | `DefaultPagination` (global), `LargeTablePagination` (keyset) (rule 17) |
| `exceptions.py` | The single API error envelope |
| `views.py` | `GET /api/health/` — public, checks Postgres and Redis |

## Using it

```python
# models/order.py
from apps.common.models import BaseModel

class Order(BaseModel):
    ...

# repositories/order_repository.py
from apps.common.repositories import BaseRepository

class OrderRepository(BaseRepository[Order]):
    model = Order

    def for_user(self, user):
        return self.active().filter(owner=user).select_related("owner")
```

`BaseRepository` gives you `active()`, `all_including_deleted()`, `get()`,
`find()`, `exists()`, `create()`, `update()`, `soft_delete()`, `restore()`,
`bulk_soft_delete()`. Add whatever else your service needs — repositories are
allowed to grow, as long as they stay free of business rules.

## Classes and methods

**`BaseModel`** (`models/base.py`) — the abstract parent of every model. A UUID key, when the
row was created and last changed, who created it, and when it was soft-deleted.
- `delete()` marks the row deleted; it never issues `DELETE`.
- `restore()` clears the mark. `is_deleted` says whether it is set.
- `purge()` really removes the row — data migrations only.

**`SoftDeleteQuerySet`** (`managers.py`) — a queryset whose `delete()` marks every row
instead of removing it. `purge()` removes for real; `alive()` and `dead()` filter on the mark.

**`SoftDeleteManager`** — the default manager (`objects`): soft-deleted rows are invisible.
**`AllObjectsManager`** — `all_objects`: every row, deleted or not.

**`BaseRepository[TModel]`** (`repositories/base.py`) — the only surface over the ORM. A
subclass names its `model` and adds the queries its service needs.
- `active()` — live rows, the default read. `all_including_deleted()` — every row.
- `get()` / `find()` — one live row, raising or returning `None`. `exists()`.
- `create()`, `update()`, `soft_delete()`, `restore()`, `bulk_soft_delete()` — writes.

**`MoneyField`** (`fields.py`) — an amount in Omani rials: a decimal to three places, sent
by the API as a string (rule 29).

**`DefaultPagination`** / **`LargeTablePagination`** (`pagination.py`) — page-number
pagination for every list, and keyset pagination for tables too large for deep offsets.

**`exception_handler`** (`exceptions.py`) — turns every DRF failure into the one error
envelope; anything DRF does not handle is logged and left to Django's 500.

**`HealthView`** (`views.py`) — `GET /api/health/`: public, reports whether Postgres and
Redis answer, 200 when both do and 503 otherwise.

## Decisions worth not re-litigating

**`objects` hides soft-deleted rows.** This is the reason `active()` is the
default read path and `all_including_deleted()` has to be asked for by name. A
repository method that bypasses `active()` needs a comment saying why.

**`delete()` never issues `DELETE`.** Both `BaseModel.delete()` and
`SoftDeleteQuerySet.delete()` set `deleted_at`. Real removal is `purge()`, which
exists for data migrations and nothing else.

**The error envelope is single-shaped on purpose.** DRF's defaults vary by
exception type; the frontend would need a special case per endpoint. Every error
comes back as `{"error": {"code", "message", "fields?"}}`. `message` is
user-facing copy and belongs to `copywriter`.

**`/api/health/` is public.** Rule 18 says auth by default; a probe that needs
credentials cannot report that the service is up. It is the deliberate
exception, and it is the only one.

## Changing anything here

A change in this directory is a change to every slice at once. `BaseModel`'s
fields, the pagination envelope and the error envelope are all part of the
frontend contract — `unifier` or `architect` signs off, and both sides move
together.
