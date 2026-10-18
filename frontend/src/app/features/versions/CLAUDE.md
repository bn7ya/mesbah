# features/versions

A project's version tree, on the project's Versions tab. The root is the base model as
downloaded; every other version stores only the change training made to it. Every signed-in
user sees the tree, what each version changed and its exports; trainers and above make a version
active, rename it, remove it, export it and remove its exports.

## Route and guard

`/projects/:projectId/versions`, a child of the project frame. The app declares it in
`app.routes.ts` through `projectFrame()`; this feature never imports `projects`. The page reads
`projectId` from the route (`paramsInheritanceStrategy: 'always'`). `versionsGuard` is
`roleGuard('viewers')`; the backend enforces the real rule (`ViewersReadTrainersWrite` on versions
and exports, `IsTrainer` for activating, `IsViewer` for changes and downloads), and the menu hides
its writing items from viewers and reviewers.

## Backend counterpart

`backend/apps/versions/` — `GET /api/versions/?project=<id>`, `PATCH|DELETE
/api/versions/<id>/`, `POST /api/versions/<id>/activate/`, `GET /api/versions/<id>/changes/`,
`GET|POST /api/versions/<id>/exports/`, `DELETE /api/versions/exports/<id>/` and
`GET /api/versions/exports/<id>/download/`. `versions.types.ts` mirrors the serializers. The error
codes `root_version_kept`, `active_version_kept` and `not_exportable` have `errors.*` entries in
this bundle. The glossary terms `gguf` and `quantization` live in the core bundle; this bundle
adds `attention`, `feed_forward` and `rank`.

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

The menu on each card: Make active (the tooltip explains rolling back), Rename (name and notes),
What changed, Show exports, Export and Remove, which asks first and is disabled, with a tooltip,
on the root and on the active version. Viewers and reviewers get the menu with only What changed
and Show exports. A refusal the server still sends shows in the page.

**What changed** opens a dialog. A change version shows a plain finding (attention or feed-forward
modules changed most, or about equally), the layers that changed most (only when there are more
than three), the parameters changed and the rank — plus the size of the change and the change from
the parent in Expert mode — then a map: a table of layers by modules, attention modules first, each
cell tinted by its norm against the version's largest cell and carrying its number. A base or a
from-scratch version has no change, so the dialog says so instead of drawing a map.

**Export** (trainers and above) asks for a format with a radio card each: LoRA adapter (a zip of
the change, change versions only), Merged model (the full model with the change folded in, change
versions only) and GGUF file (any version, with a quality choice: f16, bf16 or q8_0). A choice that
does not apply is disabled with its reason beside it. Starting it closes the dialog and opens
**Show exports**: a list of the version's exports, newest first. Each is a card with its format,
status (an icon and a word, with an indeterminate progress bar while queued or running), size, who
and when, the reason a failure gives in words, and Download (a ready LoRA or GGUF export), Copy
path (a ready merged export, which is a folder as large as the model and is not downloadable) and
Remove (asks first). The list polls every three seconds while any export is unfinished and stops
when the dialog closes.

## Classes and methods

**`VersionsApi`** (`data/versions.api.ts`) — one method per endpoint above; `tree()` and
`exports()` ask for one page of 200. `downloadUrl()` is the address a Download link points at.

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
- What changed: `showChanges()` points a resource at one version, `forgetChanges()` clears it,
  `reloadChanges()` tries again. `versionChanges`, `changeMap`, `changesLoading` and
  `changesLoadError` are `computed`.
- Exports: `showExports()` points a resource at one version (reloading when it is the open one),
  `forgetExports()` clears it, `reloadExports()` tries again. `exports`, `exportsLoaded`,
  `exportsLoading`, `exportsLoadError` and `unfinishedExports` are `computed`; `exportsWorking`
  (ids mid-request) and `exportsError` are signals.
- `createExport()` hands a refusal back to the dialog and, when the open list is that version's,
  puts the new export at its top. `removeExport()` takes it off the list and keeps a refusal in
  `exportsError`. `downloadUrl()` is the Download link's address.
- `watchExports()` is a stream the exports dialog subscribes to with `takeUntilDestroyed()`: every
  three seconds while any export is queued or running, it fetches the list quietly and replaces
  it; it goes silent when none is. A failed poll keeps the list. A poll that began before a
  removal or a new export is dropped, so a stale answer never brings back what was removed.

**`VersionsPage`** (`pages/versions/`) — the explainer, the loading and failure states and the
tree, opened on the project from its `projectId` input.

**`VersionBranch`** (`components/version-branch/`) — one version's row and, below it, a list of
its children, each a `VersionBranch`; draws the connectors.

**`VersionRow`** (`components/version-row/`) — one version as a card. Opens the rename, what
changed, exports and export dialogs with its own injector, asks before removing and reports each
change in a snack bar. After an export starts it opens the exports dialog.

**`ExportItem`** (`components/export-item/`) — one export as a card: format, status, quality, size,
the failure reason from `error_code` (an unknown code reads as a plain failure), when and by whom,
and Download, Copy path and Remove. Copies the path through the CDK `Clipboard`.

**`ChangeMapView`** (`components/change-map/`) — the layer by module map as a table. The layer
column and the header stay in view while it scrolls, and a cell's `aria-label` reads "layer 3,
q_proj: 0.12".

**`RenameVersionDialog`** (`dialogs/rename-version/`) — name (required) and notes. Sends only
what changed; closes with `true` once saved.

**`ExportVersionDialog`** (`dialogs/export-version/`) — the format and quality choice described
above. Starts the export through the store, shows a refusal in the dialog and closes with `true`
once it is queued.

**`VersionExportsDialog`** (`dialogs/version-exports/`) — a version's exports. Points the store at
the version, subscribes to `watchExports()` until it closes, forgets the list on close and opens
the export dialog for trainers.

**`VersionChangesDialog`** (`dialogs/version-changes/`) — the summary and the map, or the note for
a version that changed nothing. Points the store at the version and forgets it on close.

**`buildChangeMap()`** (`state/change-map.ts`) — turns the backend's layers and modules into the
map: modules grouped as attention, feed-forward and other, tints, the layers that changed most
and which kind of module leads. **`versionLabel()`** (`state/version-label.ts`) — "v2 · name", the
way a version is named in a title or a sentence.

**`versionsGuard`** (`guards/`) — viewers and above.

## Decisions worth not re-litigating

**The row talks to the store itself.** A branch nests to any depth, and passing four inputs and
three outputs through every level says less than a component that injects the route's store.

**The percentage is of the full model.** Every delta is measured from the base (ADR-004), so a
version's size against the base is the honest figure; a share under 0.1% reads "under 0.1%".

**The map is a native table, not `mat-table`.** It is a heat map of numbers on one scale, not
records to sort or page, and `mat-table`'s cell padding would pull the tiles apart. It is still a
real `<table>` with a caption, column and row headers.

**The darkest cell is a 48% mix, not 100%.** Each cell's text is `--mat-sys-on-surface`, and
48% is the most primary the mix can hold while that text keeps 4.5:1 in both schemes (in dark,
primary is the light tone, so a stronger mix is lighter). That is also why the map says "a
stronger colour", never "darker". `MAX_TINT` carries the number.

**"LoRA adapter", not "LoRA folder".** The export is a zip file, so the card says what a
download gets.

**An export keeps polling only while its dialog is open.** The route store outlives the page, so
the stream belongs to the dialog; closing it cancels the timer and any request in flight.

**The seeded name of a root reads as "Base model".** `VersionNamePipe` (in `shared/`) swaps the
backend's seeded `base` on version 0 for words in the reader's language; a name somebody chose
stays.
