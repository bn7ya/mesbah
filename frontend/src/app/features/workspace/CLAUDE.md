# feature: workspace (frontend)

`WorkspacePage` — the per-project shell at `/projects/:id`. The `:id` route param
binds to the `@Input() id` (component input binding).

- Loads the project + its versions; header shows name, base model, and the active
  version label (resolved from `active_version_id`).
- Hosts six panels in PrimeNG **Tabs**: `ChatPanel`, `TasksPanel`,
  `DataLabPanel`, `TrainingPanel`, `AutoEnhancePanel`, `VersionsPanel` — each
  receives `[projectId]`. Tab indices are named constants (`TAB`, module-level)
  rather than magic numbers, since two flows jump to a specific tab: the
  untrained-scratch redirect (`tab = TAB.training`) and the training panel's
  `(reviewData)` link (`tab = TAB.dataLab`).
- `reload()` re-fetches project + versions; wired to the training/versions panels'
  `(changed)` output so activating/finishing a run refreshes the header badge.
- `DataLabPanel`'s `(changed)` calls `onDataLabChanged()`, which reaches into
  `TrainingPanel` via `@ViewChild` to call its (public) `loadPreview()` — so
  curating data in one tab immediately updates the "N examples ready" count
  shown in the other, even though PrimeNG keeps both tab panels mounted (not
  lazy) rather than destroying the inactive one.

Add a new project-scoped panel here: import the component, add a `<p-tab>` +
`<p-tabpanel>`, pass `[projectId]`, and add it to the `TAB` const if other
code needs to jump to it.
