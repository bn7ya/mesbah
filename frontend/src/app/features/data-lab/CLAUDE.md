# feature: data-lab (frontend)

`DataLabPanel` — review every approved/corrected chat reply across the whole
project and bulk include/exclude what actually feeds the next training run.
Replaces the old dead-end "معاينة" (preview) dialog in the training panel,
which only showed a read-only sample with no way to act on it.

- Summary strip (`api.dataLabSummary`): total candidate replies, how many are
  currently approved+included, and — highlighted — how many **would actually
  be used in the next run** (`would_include_count`, computed backend-side by
  the exact same predicate the training dataset builder uses).
- Filter bar: status (`pending`/`approved`/`excluded`), task, "only corrected".
  All three re-run both the list and the summary query.
- `p-table` (lazy/server-paginated via `api.dataLabExamples`) — the app's
  first use of `p-table`, justified because this is genuinely tabular,
  multi-select, paginated data unlike the rest of the app's card-style lists.
  Checkbox column + bulk toolbar (اعتماد وتضمين / تضمين / استبعاد) act on the
  selection via `api.dataLabBulkUpdate`; each row also has a quick
  `p-toggleswitch` for `include_in_training` (disabled until the reply is
  approved) and a one-click "اعتماد" for pending rows.
- Rows for excluded/pending examples are dimmed (`opacity-50` when
  `!would_include`) so it's visually obvious what will and won't be used.

## Entry point
Reached as its own tab in `WorkspacePage`, positioned **before** "التدريب" —
the training panel's dataset-ready banner also emits `(reviewData)` which the
workspace turns into `tab = <data-lab index>`, so "go curate your data" is one
click away right where the user is about to start a run.

## Wiring
`(changed)` fires after any bulk/row update; the workspace re-fetches the
training panel's preview count (`ViewChild(TrainingPanel).loadPreview()`) so
the "N examples ready" banner never goes stale relative to what Data Lab shows.

## Scope (deliberately not built yet)
Reviewing and toggling only — no inline text editing of examples, no
dataset-wide stats/quality dashboards, no external JSONL import. These are
natural follow-ups, not part of this pass.
