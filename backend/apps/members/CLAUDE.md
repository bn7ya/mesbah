# apps/members

The people who use one Mesbah and their roles. The backend half of the Members page, and the
home of the role permissions every other app uses.

## Its counterpart

`frontend/src/app/features/members/` — the Members page.

## Roles

Four Django groups, created by `migrations/0001_roles.py`, ordered as a ladder. Each role can
do everything the roles below it can (rule 20: groups are the only authorization system).

| Group | Can |
|---|---|
| `viewers` | see projects, chat with versions |
| `reviewers` | also correct replies and approve them for training |
| `trainers` | also download models, add datasets, train, export, design models |
| `admins` | also manage members, the system and the engines |

A superuser is the **owner**: always an administrator, always active, and its role is not
changed here. The first-run setup creates it.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/members/` | administrator | a page of members |
| `POST` | `/api/members/` | administrator | `201` the member; `400 username_taken`, `400 weak_password` |
| `PATCH` | `/api/members/<id>/` | administrator | the member; `409 last_administrator`, `409 owner_locked`, `409 self_deactivation` |

A member — mirrored by `Member` in `features/members/data/members.types.ts`: id, username,
names, email, `role` (the highest group, or `null`), `owner`, `is_active`, `is_self`,
`last_login`, `date_joined`.

## Layers

```
views.py → services/member_service.py → repositories/member_repository.py → User / Group
```

## Classes and methods

**`roles.py`** — `Role`, the four names and `LADDER`; `highest()` picks a user's role from
their groups; `at_least()` lists a role and every role above it; `rank()` orders them.

**`RoleAtLeast`** (`permissions.py`) — allows an active user holding the role or any above it;
superusers pass. **`IsViewer`**, **`IsReviewer`**, **`IsTrainer`**, **`IsAdministrator`** are
the four permissions views use. **`ViewersReadTrainersWrite`** — viewers may read, trainers may
change: the usual rule for a library or a project. **`ViewersReadAdminsWrite`** — the same with
administrators changing (engines).

**`MemberRepository`** — lists users with their groups, finds one, checks a username, creates a
user with a hashed password, replaces a user's role group, updates fields, and counts the
active users holding a role (superusers included).

**`MemberService`**, for the acting administrator:
- `listing()` — every user, by username; `describe()` — one user as the API shows them.
- `add()` — refuses a taken username and a password Django's validators reject.
- `change()` — sets the role and the active flag; refuses to touch the owner, to let anyone
  deactivate themselves, or to leave no active administrator.

**Errors** (`services/errors.py`) — `UsernameTaken`, `WeakPassword`, `LastAdministrator`,
`OwnerLocked`, `SelfDeactivation`, each with a stable `code`.

**`MemberListView`**, **`MemberDetailView`** — the endpoints above.

## Decisions worth not re-litigating

**Users are deactivated, never deleted.** `created_by` on every table points at them.

**One role per user.** Changing a role removes the other role groups, so `highest()` and what a
user can do never disagree.
