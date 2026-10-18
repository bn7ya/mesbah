# features/projects

The Projects page and a project's pages. A project is one model being customised: it starts
from a downloaded model, keeps the instructions and reply settings every conversation starts
from, and owns the version tree. Every signed-in user sees it; trainers and above start,
change and remove projects.

## Routes and guard

- `/projects` — the list. `projectsGuard` is `roleGuard('viewers')`.
- `/projects/:projectId` — the **project frame**: the header (name as the page `<h1>`, base
  model, the active version as a chip, a link back to Projects) and a `mat-tab-nav-bar` over a
  `<router-outlet>`. Its first child, `''`, is the overview. The other tabs are children the
  **app** declares in `app.routes.ts` through `projectFrame(tabs)` — `chat` and `versions` today — because
  features never import each other. `PROJECT_TABS` (`project-tabs.ts`) lists the tabs as data
  (`path`, `labelKey`, `icon`, `role`); a later slice adds one line there, one route in
  `app.routes.ts` and one `projects.tabs.*` key.
- Child pages read `projectId` from the route. `app.config.ts` sets
  `paramsInheritanceStrategy: 'always'` so a child under `:projectId` receives it as an input.

The backend enforces the real rule (`ViewersReadTrainersWrite`); the pages hide write controls
from viewers and reviewers (`canWrite`).

## Backend counterpart

`backend/apps/projects/` — `GET|POST /api/projects/`, `GET|PATCH|DELETE /api/projects/<id>/`.
`projects.types.ts` mirrors the serializers, the page envelope included; a project carries its
active version as `{id, number, name}`. One read belongs to another app and is the only place
this feature touches it: `GET /api/models/?page_size=200` (the models a project can start from,
filtered to `ready`).

## What the pages show

- **List**: one outlined card per project — name, base model and its parameters, description
  (clamped to three lines), the active version, when it was last changed, and Open. "New
  project" for trainers and above. An empty list explains itself: start one, download a model
  first (a link to Models), or ask a trainer.
- **New project dialog**: name, base model (`mat-select` of ready models; one ready model is
  chosen already), description, instructions, and a Thinking toggle that follows the chosen
  model and is disabled, with the reason, when the model cannot think. With no ready model it
  says so and links to Models. Creating goes to the new project.
- **Overview**: About (name and description editable, base model, dates), How it replies
  (instructions, Thinking, and the three reply settings as sliders with plain names and a term
  beside each: Creativity is `temperature`, Word choice range is `top_p`, Longest reply is
  counted in `token`s), and Remove project, behind a destructive confirmation. Each of the first
  two cards saves and resets on its own; viewers see the same values as text.

## Classes and methods

**`ProjectsApi`** (`data/projects.api.ts`) — one method per endpoint above, plus the read of
the library. `readyModels()` keeps only downloaded models and the four fields the form reads.

**`ProjectsStore`** (`state/projects.store.ts`), provided by the `/projects` route — the list
page, `pageIndex`, `pageSize`, `loading`, `creating` and `error` as signals; the ready models are an `rxResource` behind `readyModels`,
`modelsLoading` and `modelsError`.
- `canWrite` is `computed` from the signed-in user.
- `visit()` empties the list and loads the first page, so no card from the last visit
  lingers; `load()` fetches a page and refreshes the models.
- `create()` returns the new project or the refusal for the dialog to show.

**`ProjectStore`** (`state/project.store.ts`), provided by the project frame's route — the open
project, its active version, `loading`, `error` and `saving`. The project is an `rxResource`
keyed by id.
- `open()` points the store at a project, reloading when it is the one already open, since
  route stores outlive their page; `reload()` tries again.
- `save()` sends a partial change and keeps the project the server answers with; `remove()`
  deletes. Both hand a refusal back instead of setting `error`.
- `activeVersion` is a `linkedSignal` over the project's own `active_version`, and follows
  `ActiveVersionChanges`, so the chip changes when the versions page makes another version
  active or renames it, without reloading the project.

**`ProjectsPage`** (`pages/projects/`) — the list and its empty states, the paginator and the
New project dialog, opened with the page's injector; a successful create shows a snack bar and
goes to the project.

**`NewProjectDialog`** (`dialogs/new-project/`) — the form above. The chosen model and the
Thinking toggle are `linkedSignal`s, so choosing another model resets the toggle to what that
model supports. Closes with the new project's id.

**`ProjectFrame`** (`pages/project-frame/`) — the header, the tabs filtered by the signed-in
user's role, and the outlet. Opens the project from its `projectId` input, shows a failure
with Try again (not for a project that does not exist), and renders tabs and outlet only once
the project is there.

**`ProjectOverview`** (`pages/project-overview/`) — the overview. Every field is a
`linkedSignal` over one value of the saved project, so saving one card never discards unsaved
edits in the other. Sends only what changed, and all three reply settings together when any of
them changed. Removing asks first, then goes back to the list.

**`projectFrame()`** (`projects.routes.ts`) — builds the frame route around the overview and the
tabs the app passes in; **`projectsGuard`** (`guards/`) — viewers and above.

## Decisions worth not re-litigating

**Two stores.** The list and the open project live and die separately, so each route provides
its own. Route stores are created once and kept, so each page starts by asking for fresh data.

**Reply settings are sliders with steps.** Temperature and `top_p` move by 0.05, the longest
reply by 16 tokens, within the backend's limits.
