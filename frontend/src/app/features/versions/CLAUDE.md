# features/versions

A project's version tree, on the project's Versions tab. The root is the base model as
downloaded; every other version stores only the change training made to it. Every signed-in
user sees the tree; trainers and above make a version active, rename it and remove it.

## Route and guard

`/projects/:projectId/versions`, a child of the project frame. The app declares it in
`app.routes.ts` through `projectFrame()`; this feature never imports `projects`. The page reads
`projectId` from the route (`paramsInheritanceStrategy: 'always'`). `versionsGuard` is
`roleGuard('viewers')`; the backend enforces the real rule (`ViewersReadTrainersWrite`,
`IsTrainer` for activating), and the page hides the menu from viewers and reviewers.

## Backend counterpart

`backend/apps/versions/` — `GET /api/versions/?project=<id>`, `PATCH|DELETE
/api/versions/<id>/`, `POST /api/versions/<id>/activate/`. `versions.types.ts` mirrors the
serializers. The error codes `root_version_kept` and `active_version_kept` have `errors.*` entries
in this bundle.

## What the page shows

A short explainer, two terms (`version`, `adapter`), then the tree. Each version is an
outlined card, filled for the active one, with: its number, name and an Active badge (icon and
word); what kind it is in words, with the `delta` term for a change; its notes; its size —
for a change a bar and "{size}, which is {percent} of the full model", for a root "{size},
stored once and not copied"; when it was made and by whom. Expert mode adds the LoRA rank,
whether biases were trained, the parameters changed and the size of the change, to two
significant digits. The tree is nested lists: indentation and connector lines are borders in
`--mat-sys-outline-variant`. A tree of only the base ends with "Train the model to add versions
here."

The menu on each card: Make active (the tooltip explains rolling back), Rename (name and notes)
and Remove, which asks first and is disabled, with a tooltip, on the root and on the active
version. A refusal the server still sends shows in the page.

## Classes and methods

**`VersionsApi`** (`data/versions.api.ts`) — one method per endpoint above; `tree()` asks for
one page of 200.

**`VersionsStore`** (`state/versions.store.ts`), provided by the route — the version list as an
`rxResource` keyed by project id, `working` (ids mid-request) and the last action `error`.
- `versions`, `tree`, `loading`, `loadError` and `canWrite` are `computed`; the tree nests each
  version under its `parent_id`, and a version whose parent is missing becomes a root.
- `open()` points the store at a project, reloading when it is the open one, since route stores
  outlive their page; `reload()` tries again. Loading follows the paginator's `next` until every
  version is here.
- `activate()` and `remove()` report success and keep a refusal in `error`; `rename()` hands its
  refusal back to the dialog. Activating clears the flag on every other row; removing loads the
  tree again so the children show under the parent.
- Every load and change tells `ActiveVersionChanges` (in `shared/`) which version is active, so
  the project frame's chip follows.

**`VersionsPage`** (`pages/versions/`) — the explainer, the loading and failure states and the
tree, opened on the project from its `projectId` input.

**`VersionBranch`** (`components/version-branch/`) — one version's row and, below it, a list of
its children, each a `VersionBranch`; draws the connectors.

**`VersionRow`** (`components/version-row/`) — one version as a card. Opens the rename dialog
with its own injector, asks before removing and reports each change in a snack bar.

**`RenameVersionDialog`** (`dialogs/rename-version/`) — name (required) and notes. Sends only
what changed; closes with `true` once saved.

**`versionsGuard`** (`guards/`) — viewers and above.

## Decisions worth not re-litigating

**The row talks to the store itself.** A branch nests to any depth, and passing four inputs and
three outputs through every level says less than a component that injects the route's store.

**The percentage is of the full model.** Every delta is measured from the base (ADR-004), so a
version's size against the base is the honest figure; a share under 0.1% reads "under 0.1%".

**The seeded name of a root reads as "Base model".** `VersionNamePipe` (in `shared/`) swaps the
backend's seeded `base` on version 0 for words in the reader's language; a name somebody chose
stays.
