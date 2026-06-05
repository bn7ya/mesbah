# feature: workspace (frontend)

`WorkspacePage` — the per-project shell at `/projects/:id`. The `:id` route param
binds to the `@Input() id` (component input binding).

- Loads the project + its versions; header shows name, base model, and the active
  version label (resolved from `active_version_id`).
- Hosts four panels in PrimeNG **Tabs**: `ChatPanel`, `TasksPanel`,
  `TrainingPanel`, `VersionsPanel` — each receives `[projectId]`.
- `reload()` re-fetches project + versions; wired to the training/versions panels'
  `(changed)` output so activating/finishing a run refreshes the header badge.

Add a new project-scoped panel here: import the component, add a `<p-tab>` +
`<p-tabpanel>`, pass `[projectId]`.
