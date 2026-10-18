# apps/training

Fine-tuning a new version. A run learns from the project's approved replies and any library
datasets chosen, starting from a version of the project; when it finishes, its adapter becomes a
new version in the tree (ADR-004). The trainer is the subprocess `python -m mesbah.train` and
talks to Django only through files (`mesbah/CLAUDE.md`, "The training contract"). The backend
half of the Training page.

## Its counterpart

`frontend/src/app/features/training/` — a project's Training tab: new run, live run view,
examples.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/training/?project=<id>` | viewer | a page of runs, newest first |
| `POST` | `/api/training/` | trainer | `202` the run, queued, from `starts_from` (else the active version), learning from `datasets` (`[{id, max_rows}]`) too; `409 nothing_to_learn`, `409 base_model_not_ready`, `409 dataset_not_ready`, `400 wrong_parent` |
| `GET` | `/api/training/plan/?project=<id>` | viewer | settings suited to this machine and model, approved replies, the fit |
| `GET` | `/api/training/examples/?project=<id>` | viewer | a page of approved replies as the conversations a run learns from |
| `GET` | `/api/training/<id>/` | viewer | one run, with its progress |
| `DELETE` | `/api/training/<id>/` | trainer | `204`; `409 run_still_going` |
| `POST` | `/api/training/<id>/cancel/` | trainer | the run, with `cancel_requested`; a waiting one stops at once, a running one at its next step |
| `GET` | `/api/training/<id>/metrics/?after_step=<n>` | viewer | a page of loss, learning rate and gradient norm by step |

A run's `status`: `queued` → `preparing` (with `stage`: data, tokenizer, model, parent) →
`training` → `saving` → `completed`, `failed` (`error_code`: `no_examples`, `out_of_memory`,
`load_failed`, `training_parts_missing`, `trainer_crashed`, `interrupted`, `bad_settings`,
`failed`) or `cancelled`.

## Layers

```
views.py → services/training_service.py → repositories/{run,metric}_repository.py
         → services/examples.py → apps.chat MessageRepository
         → apps.datasets DatasetService (the datasets a run learns)
tasks.py → services/runner.py → `python -m mesbah.train` (files in <data>/runs/<id>/)
                              → apps.datasets DatasetRepository (each dataset's JSONL)
                              → apps.serving DeploymentService.release(), apps.versions
```

## Classes and methods

**`TrainingRun`** — one run: the project, the version it starts from and the version it made,
the name and notes the new version takes, its sources, settings (`hyperparams`), whether it
becomes active when done, its status and stage, what the trainer reported (examples, skipped,
tokens, step of total, epoch, loss, a shortened sequence length after running out of memory),
the GPUs, its folder, how many event lines were read, the error, times and the cancel flag.
**`TrainingMetric`** — one logged step: epoch, loss, learning rate, gradient norm.

**`RunRepository`** — a project's runs, one with its project and base model, the unfinished
ones, the cancel flag. **`MetricRepository`** — a run's steps after one step, and recording
new ones (a step already recorded is skipped).

**`TrainingService`**, for the acting user:
- `plan()` — `defaults()` for this machine and model (rank 16, alpha 32, two epochs, a longer
  sequence on 24 GB and more, 4-bit only when the model would not fit in half precision), the
  approved replies, the QLoRA fit and the GPUs.
- `create()` — refuses a base model not downloaded and a run with nothing to learn, starts from
  the active version unless told otherwise, and queues the task after the commit.
- `chosen_datasets()` — the datasets a run learns, each ready (`dataset_not_ready` otherwise),
  stored with its name, its rows and the row limit.
- `cancel()`, `remove()` (finished runs only), `metrics_of()`, `listing()`, `find()`,
  `describe()`.

**`ExampleService`** — approved replies as training rows: `corrections()`, `example()` (the
prompt, the earlier turns and the reply, each reply's thinking as `thinking`), `describe()` for
the Examples tab, `write()` to a JSONL file.

**`RunnerService.run()`** — the `training.run` task's body: writes the project's approved
replies to a file (each dataset's own JSONL is read in place, up to its row limit) and `config.json`, asks the built-in engine to free the GPU, starts the trainer (`--fake` when
`MESBAH_FAKE_TRAINER`), reads `events.jsonl` every two seconds into the run and its metrics,
creates the cancel file when asked, and settles from `status.json`: the adapter moves to
`<data>/versions/<project>/<version>/` and becomes a version (made active when asked), or the
run ends failed or cancelled. A run found
already started is marked `interrupted`.

**`train`** (`tasks.py`) — the task, on the `heavy` queue that one worker serves one at a time.

## Decisions worth not re-litigating

**One run at a time, by queue.** The `heavy` queue has one solo worker (`mesbah start` starts
it; Docker's `worker-heavy`), so a second run waits instead of fighting for the GPU.

**The trainer is a subprocess that never imports Django.** A crash, an out-of-memory kill or a
CUDA fault ends the trainer, not the worker; the files say how far it got.

**Corrections are read at the start of a run.** A reply approved while a run trains goes into
the next one.
