# feature: models (frontend)

`ModelsPage` — pick the base model **live from the HuggingFace API** (no
hardcoded list), download it locally, and track progress.

- Header + HF-token hint row → links to `/settings` (the token is what lets
  gated models/datasets download).
- Two searches: models (`api.searchModels`) and datasets (`api.searchDatasets`)
  — the dataset corpus is for from-scratch training and is picked in the
  projects wizard, so it is only browsed here.
- Featured sections, straight from the hub: most-downloaded `text-generation`
  (`api.featuredModels()`) + Arabic (`api.featuredModels('ar')`). When the hub
  is unreachable the endpoint falls back to the local models — a
  `source === 'local'` row in the featured list drives the amber offline note,
  and the Arabic section filters those rows out.
- Every hub row: `repo_id` (LTR), `gated` tag, `ModelFitBadge` (fit against the
  detected hardware — `core/model-fit-badge`), params/license/downloads chips,
  and one shared download cell (`#dl` `ng-template`, keyed `type:repo`).
- Download: `api.downloadModel`/`api.downloadDataset` then poll
  `api.downloadStatus`/`api.datasetDownloadStatus` every 1.5 s until
  `done`/`error` (per-key `downloads` signal, `timers` map); on a model
  `done` the local list refreshes (`api.localModels`) and a success toast fires.
- Local section lists what is on disk with its GB size (`gb()` formats bytes).

`DownloadState` (status/bytes_done/total_bytes/percent/error) is local to this
file. `dlState()` resolves a row to its download state, treating anything in
the local list as already `done`.
