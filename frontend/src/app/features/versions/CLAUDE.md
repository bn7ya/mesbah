# feature: versions (frontend)

`VersionsPanel` — visualize and manage the model **version tree**.

- Fetches `api.versionTree` (nested) and flattens it via DFS into rows with
  `depth` (used for indentation + connector glyphs) — no recursive component.
- Each node shows label, `أساسي`/`نشط` tags, created date, `train_loss`, adapter ✓.
- Actions: **تفعيل (activate/rollback)** → `api.activateVersion` then `(changed)`;
  **delete** (non-base) with a confirm dialog → `api.deleteVersion`.
- Footer explains the mental model: training appends under the active node;
  activating an older node = rollback; training from a mid node = branch.

To render the tree as true 2-D graph edges instead of indented rows, replace the
flatten + row layout here (keep the `(changed)` emits).
