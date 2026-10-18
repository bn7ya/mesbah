# The Design Pattern

**Vertical Slice + Service/Repository.** This is the only pattern used in this project. Every agent cites this document. Deviating requires an ADR in `.claude/docs/adr/`.

---

## 1. The slice

A feature is one vertical slice spanning the whole stack. It is never "a frontend task" or "a backend task".

```
frontend/src/app/features/<feature>/     ⟷     backend/apps/<feature>/
```

The names match. One Angular feature directory mirrors exactly one Django app, and both mirror one page (or one tightly-related group of pages) in the product.

A slice is complete when all of these exist:

| # | Layer | File |
|---|---|---|
| 1 | Route | `<feature>.routes.ts` |
| 2 | Guard | `guards/<feature>.guard.ts` |
| 3 | Page component | `pages/<page>/<page>.{ts,html,scss}` |
| 4 | State | `state/<feature>.store.ts` (signals) |
| 5 | API client | `data/<feature>.api.ts` |
| 6 | Types | `data/<feature>.types.ts` |
| 7 | i18n keys | `i18n/{en,ar}.json` entries |
| 8 | Frontend memory | `features/<feature>/CLAUDE.md` |
| 9 | URL conf | `apps/<feature>/urls.py` |
| 10 | View | `apps/<feature>/views/<name>.py` |
| 11 | Serializer | `apps/<feature>/serializers/<name>.py` |
| 12 | Permission | `apps/<feature>/permissions.py` |
| 13 | Service | `apps/<feature>/services/<name>_service.py` |
| 14 | Repository | `apps/<feature>/repositories/<name>_repository.py` |
| 15 | Model | `apps/<feature>/models/<name>.py` |
| 16 | Migration | `apps/<feature>/migrations/` |
| 17 | Backend memory | `apps/<feature>/CLAUDE.md` |

If a change touches only one side, it is not a slice — it is an incomplete change. Say so and finish the other side.

---

## 2. Backend layering

Four layers, strictly one-directional. **A layer may only call the layer directly below it.**

```
View  ──►  Service  ──►  Repository  ──►  Model / ORM
 │
 └── Serializer (shape only, no logic)
```

### View — thin
Parses the request, delegates to exactly one service call, returns a serialized response. No business rules, no ORM access, no `if` chains over domain state.

```python
class OrderListView(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OrderService(self.request.user).list_visible()
```

### Serializer — shape only
Field mapping and field-level validation. No DB queries, no cross-object rules, no side effects. Object-level rules belong in the service.

### Service — business logic
Owns rules, orchestration, transactions and permission decisions beyond the route level. Takes the acting user in its constructor. Returns domain objects or querysets. Never touches `Model.objects` — it calls repositories.

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
Every `.objects.` call in the codebase lives in a `repositories/` module. This is enforced by `.claude/hooks/guard-checks.py`. Repositories return querysets or model instances and contain no business rules.

```python
class OrderRepository(BaseRepository):
    model = Order

    def get_for_user(self, order_id: UUID, user) -> Order:
        return self.active().filter(owner=user).get(pk=order_id)
```

`BaseRepository` (in `apps/common/repositories/base.py`) supplies `active()`, `all_including_deleted()`, `get()`, `create()`, `update()`, `soft_delete()`.

**No raw SQL in application code.** If the ORM genuinely cannot express it, put the SQL in a repository method with a comment explaining why, and have `db_engineer` sign off with benchmark numbers.

---

## 3. Frontend layering

Mirror image, same one-directional rule.

```
Component  ──►  Store (signals)  ──►  Api client  ──►  HttpClient
```

### Component — presentation
Reads signals, renders, emits user intent to the store. No `HttpClient`, no business rules, no data transformation beyond formatting.

- Standalone. Always.
- `.ts`, `.html` and `.scss` are always three separate files. Never inline `template:` or `styles:`.
- State is signals — `signal`, `computed`, `linkedSignal`, `resource`. Do not use `BehaviorSubject` for view state.
- No `setTimeout`. If you need to defer, model it in state.
- Angular Material for every control — `matButton` and `matIconButton` on a native `<button>` or `<a>`, `mat-form-field` with `matInput`, `mat-card`, `mat-button-toggle-group`, `MatDialog`, `mat-select`, `mat-table` — each imported into the standalone component that uses it. A control Material lacks, needed by two features, becomes a component in `shared/` on the CDK. Never `confirm()`, `alert()` or `prompt()`: `MatDialog` asks, `MatSnackBar` or a message in the page reports, a form field collects.

### Store — feature state
Holds signals, exposes `computed` derivations, calls the api client, owns loading/error state. One store per feature.

```ts
@Injectable()
export class OrdersStore {
  private readonly api = inject(OrdersApi);

  readonly orders = signal<Order[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly submittable = computed(() => this.orders().filter(o => o.canSubmit));
}
```

### Api client — transport
One method per endpoint. Maps wire types to domain types. No caching, no state, no error UI decisions.

---

## 4. Shared foundations

### `BaseModel` — every model inherits it

```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    objects = SoftDeleteManager()        # excludes soft-deleted rows
    all_objects = models.Manager()       # includes them

    class Meta:
        abstract = True
```

### Soft delete only

`delete()` on a `BaseModel` sets `deleted_at`. It never issues `DELETE`. Hard deletion is a data-migration decision, never an application one.

### Pagination on every list endpoint

`DEFAULT_PAGINATION_CLASS` is set globally in `config/settings/base.py`. A list endpoint that opts out needs a comment saying why.

### Auth by default

`DEFAULT_PERMISSION_CLASSES = ["rest_framework.permissions.IsAuthenticated"]`. A public endpoint declares `permission_classes = [AllowAny]` explicitly — it is opt-out, never opt-in.

Authorization is **Django Groups and Permissions**. There is no parallel role system. The frontend reads the same group names from `/api/auth/me/` and uses them in route guards and to show or hide affordances. A permission check that exists on the frontend must also exist on the backend; the frontend check is a convenience, the backend check is the security boundary.

### File splitting

`models.py`, `views.py`, `serializers.py` become packages once they hold more than about three items:

```
models/
  __init__.py      # from .order import Order   — re-export everything
  order.py
  order_line.py
```

Importers always use `from apps.orders.models import Order`, never the submodule path.

---

## 5. Styling

One source of truth: **the Angular Material theme**, in `src/styles/`. ADR-002 records the
decision.

| File | Holds |
|---|---|
| `_theme.scss` | `mat.theme()` — colour from the brand palettes, Tajawal, density — so every `--mat-sys-*` token; the strong focus indicators; every `mat.<component>-overrides()` |
| `_theme-colors.scss` | The M3 palettes, generated from the brand gold by `ng generate @angular/material:theme-color` — regenerated, never edited |
| `_tokens.scss` | Only what Material has no system token for, as `--app-*`: the space scale, the focus width, the icon box, a duration, an easing, a layer |
| `_reset.scss` | Box sizing, margins, reduced motion |
| `_base.scss` | Element defaults: body type, headings, links, the focus ring for what is not Material, `.text-secondary`, the skip link |
| `_layout.scss` | The page's maximum widths and the shell's breakpoints |

`src/styles.scss` uses them in that order (layout is pulled in by the components that need
it). Colour, type, shape and elevation are read as `var(--mat-sys-*)`; spacing as
`var(--app-space-*)`. **No raw px in feature styles** — enforced by the guard hook. A
component that needs a value writes a token, never a number. A value the system does not
have is a theme override or an `--app-*` token, which is a decision for the whole app, not a
feature.

A feature stylesheet places Material components — their size, gap and padding in the page —
and never restyles one. How every button, field or card looks changes in `_theme.scss`,
through `mat.<component>-overrides()`.

`mat.strong-focus-indicators()` draws the ring on every Material control and `_base.scss`
draws the same ring on everything else, both in `--mat-sys-primary`. A component that writes
its own `outline` on `:focus-visible` replaces that ring rather than adding to it, which is
why none of them do.

Three files are exempt from the px rule, and only three: `_tokens.scss`, where the `--app-*`
values are defined; `_layout.scss`, because a media query cannot read a custom property; and
`_reset.scss`. Breakpoints are viewport media queries through the `from($screen-md)` mixin;
a component that has to answer to its own width may use a container query inside itself.

Visual hierarchy is a rule, not a preference: the most important information on a screen
renders largest. `.claude/docs/interface.md` is the standard for that and everything beside
it — states, type, the two schemes, depth, icons. `interface_designer` owns it and
`unifier` audits against it.

Nothing else. No second component library and no utility-class framework, Tailwind
included, is ever added alongside this. Either bypasses the theme and becomes a second,
competing source of truth for exactly the values `mat.theme()` already owns. If the visual
language needs to change, the theme changes — not the toolkit.

---

## 6. Definition of done

A slice is done when:

- [ ] All 17 files from §1 exist (or their absence is justified in the feature's `CLAUDE.md`)
- [ ] Both `CLAUDE.md` files are written or updated
- [ ] Every string is in `en.json` and `ar.json`, and the UI works in RTL
- [ ] The endpoint appears correctly in `/api/schema/swagger-ui/`
- [ ] Auth is enforced server-side and reflected in the route guard
- [ ] List endpoints paginate
- [ ] No hardcoded px, no `setTimeout`, no native browser dialogs, no hand-rolled focus ring
- [ ] Every control is Angular Material, and none is restyled outside `_theme.scss`
- [ ] No `.objects.` outside a repository, no raw SQL, no hard delete
- [ ] Nothing deprecated; nothing unused left behind
