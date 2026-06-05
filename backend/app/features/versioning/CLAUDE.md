# feature: versioning (model version tree)

The version tree makes fine-tuning **reversible and branchable**. Each
`ModelVersion` is a node; `parent_id` links it to the node it was trained from.

## Files
- `service.py` — `list_versions`, `build_tree` (nested dicts), `create_child`
  (used by training), `set_active` (activate/rollback), `delete_version`.
- `router.py` — `/api/projects/{id}/versions`, `/version-tree`,
  `/versions/{vid}/activate`, `PATCH/DELETE /versions/{vid}`.

## Semantics
- **enhance** = train from the active node → new child node (training feature).
- **reverse / rollback** = `set_active` an older node (also sets
  `project.active_version_id`; exactly one node active at a time).
- **branch** = train from any non-tip node.
- The **root** node is `is_base=True`, `parent_id=None`, created with the project.

## Gotchas
- `delete_version` re-parents children onto the deleted node's parent, nulls any
  `TrainingRun` references, falls back to the base node if the active one is
  removed, then deletes — all under `PRAGMA defer_foreign_keys` + `flush()`.
  **Cannot delete the base node.**
- `depth` is maintained on insert and used by the GUI to indent the tree.
