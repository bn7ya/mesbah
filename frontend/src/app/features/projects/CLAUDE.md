# feature: projects (frontend)

`ProjectsPage` — landing page: grid of project glass-cards + "new project" dialog
with the **curated model picker**.

- Loads `api.listProjects()` and `api.curatedModels()`.
- New-project dialog: selectable model cards (badges: params, context, Arabic,
  license; "موصى به" for `recommended`), name + description, then
  `api.createProject` → navigate to `/projects/:id`.
- Empty state invites creating the first project.

Edit here to change the project list, card layout, or the create flow / model
picker presentation. Card stats (sessions/tasks/versions) come from `ProjectRead`.
