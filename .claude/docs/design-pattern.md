# The Design Pattern

**Vertical Slice + Service/Repository**, on the Django side, ported from
`bn7ya/template` per the root `CLAUDE.md`. Every agent in `.claude/agents/`
cites this document. Deviating requires an ADR in `.claude/docs/adr/`.

This doc governs the **Django migration target** (`backend/apps/`) and the
**existing Angular frontend** (`frontend/src/app/`) as it actually is today —
it does not invent a frontend architecture the project doesn't have. Read
`frontend/CLAUDE.md` and `backend/CLAUDE.md` alongside this before touching
either side.

## 0. Which backend you are touching

Mesbah runs **two backends side by side** during the migration:

- **`backend/app/`** (FastAPI + SQLModel + SQLite) — the **live** backend.
  The Angular app talks to this one today, over `/api/*` via the dev proxy.
  It is a working product, not legacy code — features still get added here.
- **`backend/apps/` + `backend/config/`** (Django + DRF + PostgreSQL/pgvector
  + Redis + Celery) — the **migration target**. Independently verified
  (migrations, DRF schema, tests) but **nothing in it is wired to the
  Angular app yet**. Sections 2 and 4 below describe this side.

Before writing a line of backend code, know which one you're in. A request
like "add a field to the project model" almost always means `backend/app/`
(that's the one users hit); "port projects to Django" means `backend/apps/`.
Don't assume — check `backend/CLAUDE.md`'s phase list, or ask.

---

## 1. The slice

A feature is one vertical slice spanning Django and Angular. It is never
"a backend task" or "a frontend task" in isolation — but the two sides are
**not symmetric**, because the frontend already has its own established,
simpler shape that the migration does not change.

```
frontend/src/app/features/<feature>/     ⟷     backend/apps/<feature>/
```

The names match — this is the one rule the two sides share, already in
force per `backend/apps/common/CLAUDE.md`: **one Django app per Angular
feature** (`apps/common` is the deliberate, documented exception).

A slice touching the Django side is complete when all of these exist:

| # | Side | File |
|---|---|---|
| 1 | Backend | `apps/<feature>/models/<name>.py` — inherits `BaseModel` |
| 2 | Backend | `apps/<feature>/repositories/<name>_repository.py` |
| 3 | Backend | `apps/<feature>/services/<name>_service.py` |
| 4 | Backend | `apps/<feature>/views/<name>.py` |
| 5 | Backend | `apps/<feature>/serializers/<name>.py` |
| 6 | Backend | `apps/<feature>/permissions.py` (if not just `IsAuthenticated`) |
| 7 | Backend | `apps/<feature>/urls.py` |
| 8 | Backend | `apps/<feature>/migrations/` |
| 9 | Backend | `apps/<feature>/CLAUDE.md` |
| 10 | Frontend | `frontend/src/app/features/<feature>/<feature>-*.ts` — standalone, signals |
| 11 | Frontend | a method per endpoint added to the **shared** `core/api.ts` |
| 12 | Frontend | the response shape added to the **shared** `core/types.ts` |
| 13 | Frontend | `frontend/src/app/features/<feature>/CLAUDE.md` |

Rows 10–13 are deliberately few — see §3. If a change touches only one
side, it is not a slice; say so and finish the other side, unless it is
genuinely one-sided (a pure Django-internal refactor, a pure copy change) —
in which case say that explicitly rather than leaving it unsaid.

---

## 2. Backend layering (Django side, `backend/apps/`)

Four layers, strictly one-directional. **A layer may only call the layer
directly below it.**

```
View  ──►  Service  ──►  Repository  ──►  Model / ORM
 │
 └── Serializer (shape only, no logic)
```

### View — thin
Parses the request, delegates to exactly one service call, returns a
serialized response. No business rules, no ORM access, no `if` chains over
domain state.

```python
class OrderListView(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OrderService(self.request.user).list_visible()
```

### Serializer — shape only
Field mapping and field-level validation. No DB queries, no cross-object
rules, no side effects. Object-level rules belong in the service.

### Service — business logic
Owns rules, orchestration, transactions and permission decisions beyond the
route level. Takes the acting user in its constructor. Returns domain
objects or querysets. Never touches `Model.objects` — it calls repositories.

```python
class OrderService:
    def __init__(self, user):
        self.user = user
        self.orders = OrderRepository()

    @transaction.atomic
    def submit(self, order_id: UUID) -> Order:
        order = self.orders.get_for_user(order_id, self.user)
        if not order.is_submittable():
            raise ValidationError("This order can no longer be submitted.")
        return self.orders.mark_submitted(order)
```

### Repository — the only place the ORM is touched
Every `.objects.` call in `apps/*` lives in a `repositories/` module —
enforced by `.claude/hooks/guard-checks.py`. Repositories return querysets
or model instances and contain no business rules.

```python
class OrderRepository(BaseRepository):
    model = Order

    def get_for_user(self, order_id: UUID, user) -> Order:
        return self.active().filter(owner=user).get(pk=order_id)
```

`BaseRepository` (`apps/common/repositories/base.py`) supplies `active()`,
`all_including_deleted()`, `get`/`find`/`exists`, `create`/`update`,
`soft_delete`/`restore`/`bulk_soft_delete`.

**No raw SQL in application code.** If the ORM genuinely cannot express it,
put the SQL in a repository method with a comment explaining why, and have
`db_engineer` sign off with benchmark numbers.

---

## 3. Frontend layering (`frontend/src/app/`) — as it actually is

Mesbah's Angular app is intentionally **flatter** than a per-feature
store/api/types split. This is not a gap to fill in — it is the documented
convention (`frontend/CLAUDE.md`), and it does not change when the backend
moves to Django.

```
Component (signals)  ──►  the ONE shared core/api.ts  ──►  HttpClient
```

- **One API gateway.** `core/api.ts` is the single typed gateway to the
  backend for every feature — inject it, never sprinkle `HttpClient` in a
  component. Adding an endpoint means adding one method here, not a new
  per-feature `data/<feature>.api.ts`.
- **One types file.** `core/types.ts` mirrors the backend schemas for every
  feature. Add the new shape here, not a per-feature `data/<feature>.types.ts`.
- **Component — presentation and state.** Standalone, always. Signals
  (`signal`, `computed`) for state, `inject()` for deps — no `NgModule`,
  no constructor injection, no `BehaviorSubject` for view state. A
  component's `template:`/`styles:` are inline (Tailwind utility classes,
  no `.scss` file) — see `frontend/CLAUDE.md`, this is deliberate, not a
  shortcut to fix.
  - No `setTimeout`. Model timing in state.
  - No native browser UI: never `confirm()`, `alert()`, `prompt()`,
    `<dialog>`, or a bare `<input type="radio">`. PrimeNG has all of these
    (`p-confirmdialog`, `p-toast`/`p-message`, `p-dialog` + `p-inputtext`,
    `p-radiobutton`).
- **Routing.** `app.routes.ts` is one flat list (no per-feature
  `<feature>.routes.ts`, no guards — mesbah is single-user with no
  role-based UI gating; the Django migration adds auth at the API layer,
  not per-route frontend guards).
- **Language.** Mesbah's UI is Arabic, RTL, single-language — there is no
  `en.json`/`ar.json` parity to maintain. Technical terms (`QLoRA`, `LoRA`,
  `adapter`, `base model`, `loss`, `VRAM`, …) stay in **English**, wrapped in
  `code.ltr`; everything else is Arabic. Use logical utilities (`ps-*`,
  `pe-*`, `ms-*`, `me-*`, `text-start`) — never assume LTR.

---

## 4. Shared foundations (Django side)

### `BaseModel` — every model inherits it

Already implemented in `apps/common/models/base.py`:

```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    objects = SoftDeleteManager()        # excludes soft-deleted rows
    all_objects = AllObjectsManager()    # includes them

    class Meta:
        abstract = True
```

### Soft delete only

`delete()` on a `BaseModel` sets `deleted_at` (`.purge()` is the one real
delete, reserved for data migrations — see `apps/common/models/base.py`).

### Pagination on every list endpoint

`DEFAULT_PAGINATION_CLASS` (`apps/common/pagination.py::DefaultPagination`)
is set globally. A list endpoint that opts out needs a comment saying why.
`LargeTablePagination` (cursor-based) exists for deep-offset tables — not
needed yet at Mesbah's single-user scale.

### Auth by default

`DEFAULT_PERMISSION_CLASSES = ["rest_framework.permissions.IsAuthenticated"]`.
A public endpoint declares `permission_classes = [AllowAny]` explicitly.

Authorization is **Django Groups and Permissions** — no parallel role
system. Mesbah stays single-user (one seeded operator account per the root
`CLAUDE.md`), so this is a security boundary, not a UI-gating mechanism: the
frontend does not currently branch on group membership.

### File splitting

`models.py`, `views.py`, `serializers.py` become packages once they hold
more than about three items, re-exporting from `__init__.py`. Importers use
`from apps.<feature>.models import Thing`, never the submodule path.

---

## 5. Styling (frontend)

One source of truth: **Tailwind v4 utility classes**, inline in each
component's `template:` — there is no `_golden.scss` token file and no
custom design system (`frontend/CLAUDE.md`).

Shared vocabulary, kept consistent across features:

- Cards: `rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900`
- Muted text: `text-neutral-500 dark:text-neutral-400`
- Accent: blue (`text-blue-600 dark:text-blue-400`, `bg-blue-600` buttons)
- Thin borders, no heavy shadows; selected/active state is a blue ring
  (`ring-1 ring-blue-400/40`)
- Dark mode is class-based (`.dark` on `<html>`)

Visual hierarchy is still a rule, not a preference: the most important
information on a screen renders largest. There is no φ ladder to consult —
use Tailwind's own type/spacing scale deliberately and consistently.

---

## 6. Definition of done

A slice touching the Django side is done when:

- [ ] The rows in §1 that apply exist (or their absence is justified in the
      feature's `CLAUDE.md`)
- [ ] Both `CLAUDE.md` files (backend app + frontend feature) are written
      or updated
- [ ] The endpoint appears correctly in `/api/schema/swagger-ui/`
- [ ] Auth is enforced server-side (`permission_classes`)
- [ ] List endpoints paginate
- [ ] No `.objects.` outside a repository, no raw SQL, no hard delete
- [ ] No `setTimeout`, no native browser dialogs, in any touched component
- [ ] The UI still works in RTL and technical terms stayed in English
- [ ] Nothing deprecated; nothing unused left behind
