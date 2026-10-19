# frontend/e2e

The release journeys: Playwright against a real `mesbah start`, in English (left to right) and
Arabic (right to left), as a person would use Mesbah (ADR-010). They are part of the release
bundle and run on every release tag and nightly. Normal CI only type-checks and lints them.

## How they run

Nothing here needs a GPU, torch or the network:
- **Training** is Mesbah's fake trainer (`MESBAH_FAKE_TRAINER=1`).
- **Chat** is the fake engine (`python -m mesbah.runtime --fake`), which listens where the
  built-in engine would, so Django loads versions and streams replies exactly as it does for a
  real one.
- **The base model** is trained here by the setup journey, from an uploaded dataset, with the
  Architect. HuggingFace is never needed, and the stack runs with `HF_HUB_OFFLINE=1` and a dead
  proxy.

```bash
cd frontend
# Starts a stack from the checkout (build the app into the wheel folder first:
# python ../backend/tools/build_wheel.py), runs everything, stops it.
E2E_PYTHON=../backend/.venv/bin/python npm run e2e

# Against an install, as the release bundle does, with another PostgreSQL (root can't run the
# embedded one), and a browser that isn't Playwright's own.
E2E_MESBAH=/path/to/venv/bin/mesbah E2E_DATABASE_URL=postgresql://… \
E2E_CHROMIUM=/opt/pw-browsers/chromium npm run e2e

# Attach to a stack started by `python -m tools.release.stack start`; it is left running.
E2E_STACK=/path/to/stack.json npm run e2e

npm run e2e:smoke          # only the journeys tagged @smoke
npm run typecheck:e2e      # what CI runs
```

Everything a run leaves goes in `test-results/e2e/` (`E2E_RESULTS` moves it):
- `stack/`: `stack.json` and the logs;
- `data/`;
- `world.json` and `auth/`, each role's session;
- `screens/`;
- `report/`;
- `junit.xml`;
- `artifacts/`: traces and videos of failures.

## Projects

| Project | Runs | After |
|---|---|---|
| `setup` | `journeys/setup.setup.ts`: first run in Arabic with the printed code, then the world through the API | — |
| `ltr` | `journeys/*.spec.ts` in English | `setup` |
| `rtl` | the same in Arabic | `setup` |
| `trains-ltr`, `trains-rtl` | `journeys/trains/*.spec.ts`, one at a time, English then Arabic | `ltr`, `rtl` |

Chat refuses while any training run is past `queued`, because they would share the memory. So a
journey that trains goes in `journeys/trains/`, which runs alone after everything that chats.

**The world** (`world.json`) is what the setup journey leaves. Its parts:
- **People:** the owner and a reviewer, a trainer and a viewer, each with a saved session.
- **A dataset** of twelve conversations with thinking.
- **The base model** trained from it, `local/<slug>`.
- **Three projects per language:**
  - `chat`, with only its base;
  - `versions`, with v1 and a v2 grown from v1;
  - `exports`, with v1.

A journey reads what it needs and makes anything it changes itself, so journeys never depend on
each other's order.

## Rules for a journey

- **Selectors come from the real bundles**, through `t(bundle, key, values)`, never hand-written
  in one language. A renamed key fails loudly, and the same test reads in both languages.
- **No waiting for time.** Use `expect`, `expect.poll` or `api.until()`. ESLint and the guard
  hook refuse `waitForTimeout` and `setTimeout`, and the guard reads `test.setTimeout` as
  `setTimeout`, so a long test calls `test.slow()`.
- **No `confirm`, `alert` or `prompt` names**, even in test titles' code, because of the same
  guard.
- **A page that logs an error fails its test.** A test that expects failed requests sets
  `test.use({ allowConsoleErrors: true })`.
- **`shot(name)` saves a screenshot** for the release's reference artifact. Screenshots are
  kept for people to compare, never compared pixel by pixel.
- **Types live in `*.types.ts`**, as everywhere else (rule 30).

## Classes and methods

**`readStack()`** (`harness/stack.ts`) — the running stack from `stack.json`: addresses, data
folder, setup code, version, process ids. **`FRONTEND`**, **`BACKEND`**, **`RESULTS`**,
**`STACK_FILE`**, **`PORT`** — where things are, from `E2E_RESULTS`, `E2E_STACK` and `E2E_PORT`.

**`label()`**, **`contains()`**, **`text()`**, **`template()`** (`harness/copy.ts`):
- `label()` is a bundle string as a regular expression for an accessible name or a label. It is
  anchored, tolerates the bidi isolates the page puts around filled-in values, and tolerates a
  required field's asterisk.
- `contains()` is the same, unanchored.
- `text()` is the filled-in string, and `template()` the raw one.

**`MesbahApi`** (`harness/api.ts`) — a signed-in API session over Playwright's request context:
- `open()` primes the CSRF cookie, and `signIn()` signs in.
- `get()`, `post()`, `patch()`, `delete()` and `call()` throw on any status that is not a
  success.
- `send()` returns the raw response, for checking a refusal.
- `upload()` posts a file.
- `until()` asks again until a condition holds.
- `saveState()` writes the session for a browser.

**`isJson()`**, **`field()`**, **`rows()`** narrow what the API returns, with no casts.

**`addMember()`**, **`uploadDataset()`**, **`pretrainBase()`**, **`createProject()`**,
**`trainVersion()`**, **`finished()`** (`harness/seed.ts`) — the world's building blocks, each
waiting until what it made is ready. **`CHAT_ROWS`**, **`jsonl()`** and **`PASSWORD`** are the
data they use.

**`readWorld()`**, **`writeWorld()`**, **`stateFile()`** (`harness/world.ts`) — the world and each
role's saved session.

**`test`**, **`expect`** (`harness/fixtures.ts`) — Playwright's, with:
- **Options:** `uiLocale` (the language the app opens in, set before the page loads; `null`
  leaves a first visit to choose) and `allowConsoleErrors`.
- **Values:** `locale` (the language in effect), `t` (`label()` in that language), `stack` and
  `world`.
- **Helpers:**
  - `owner`, the owner's `MesbahApi`;
  - `as(role)`, a page signed in as another role;
  - `shot(name)`.
- **`consoleGuard`**, which fails a test whose page logged an error.

**`globalSetup()`** (`global-setup.ts`) — starts a stack with `tools.release.stack` unless
`E2E_STACK` names one, and stops it afterwards.
