# ADR-008: Code outside Django lives in the `mesbah` package

**Status:** accepted — 2026-10-18 (#5)

## Context

Some of Mesbah runs where Django is not set up: the command-line launcher that starts the
database and the servers, the built-in engine process that holds a model, the training and
export subprocesses, and probes that a CLI and a web view both need. The Template has no place
for such code; `apps/` is for Django apps, one per page.

## Decision

- `backend/mesbah/` is a plain Python package beside `apps/` and `config/`.
- It never imports `apps` or `config`. The one exception is the CLI's bootstrap, which sets up
  Django before handing over to `manage.py` commands.
- Django apps may import it. A service calls `mesbah.hardware` the way it calls a library.
- It is application code: rule 30 typing, rule 31 comments, ruff, mypy and the guard hook all
  apply, and it carries a `CLAUDE.md` with "Classes and methods".
- Its tests live in `mesbah/tests/` and run in the same `pytest`.

## Consequences

The training and engine subprocesses can be started with only the package and the ML stack,
and the ML stack is never imported by the web process.
