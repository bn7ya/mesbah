# ADR-006: Served over ASGI; replies stream, jobs are polled

**Status:** accepted — 2026-10-18 (#8)

## Context

A model's reply arrives token by token over seconds or minutes, and training runs for hours.
The Template serves Django with gunicorn's WSGI workers, which hold a worker per open stream,
and has no push channel to the browser.

## Decision

- **uvicorn serves `config.asgi`** in every mode: `--reload` in development, workers behind nginx
  in production, one process in pip mode. `ASGIStaticFilesHandler` serves static files when
  `DEBUG` is on, as runserver did.
- **Database connections come from psycopg's pool** (`OPTIONS.pool`) with `CONN_MAX_AGE = 0`,
  as Django requires under ASGI.
- **Token streams** use a plain DRF view that validates and authorises, then returns a
  `StreamingHttpResponse` over an async generator. The browser reads it with `HttpClient`
  (`withFetch()`, `observe: 'events'`), so the CSRF and error interceptors still apply.
- **Long jobs are polled**: the page asks for new progress on a timer and stops when the job is
  done. No Channels, no `LISTEN/NOTIFY` (raw SQL is banned), no extra broker for the browser.

## Consequences

- A view that streams must not touch `request.user` inside the generator; it takes what it needs
  before returning.
- nginx must not buffer streams; a streaming response sets `X-Accel-Buffering: no`.
