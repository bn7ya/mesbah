# features/members

The Members page: administrators add people, change their role, and deactivate or reactivate
them.

## Route and guard

`/members`. `membersGuard` is `roleGuard('admins')`; the backend checks the same role on
every endpoint (`IsAdministrator`). The menu shows the page to administrators only.

## Backend counterpart

`backend/apps/members/` — `GET|POST /api/members/`, `PATCH /api/members/<id>/`.

## Classes and methods

**`MembersApi`** (`data/members.api.ts`) — list a page, add, change.

**`MembersStore`** (`state/members.store.ts`), provided by the route — the current page,
`pageIndex`, `pageSize`, `loading`, `busy` and the last `error`.
- `load()` fetches a page and remembers which.
- `add()` creates a member and reloads the page; it hands a refusal back to its caller (the
  dialog shows it) rather than setting the page error.
- `change()` sends a role or active change and replaces only that row.

**`MembersPage`** (`pages/members/`) — a table of members: who they are, a role menu (each role
with what it can do), the status and the deactivate or reactivate action, with a paginator.
The owner's role and the user's own account cannot be changed from here. Deactivating asks
first.

**`AddMemberDialog`** (`dialogs/add-member/`) — username, password, role (with what it can do
underneath), names and email. Opened with the page's injector so it shares the route's store;
closes with `true` once the member exists.

**`membersGuard`** (`guards/`) — administrators only.

## Decisions worth not re-litigating

**The role is a menu, not a select.** A refused change (the last administrator) must leave
the row showing the role it still has; a menu renders only what the server returned.
