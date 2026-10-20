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

# Only the journeys in journeys/alone/, on a fresh world, without every ltr and rtl journey first.
npm run e2e -- --no-deps --workers=1 --project=setup --project=alone-ltr --project=alone-rtl
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
| `alone-ltr`, `alone-rtl` | `journeys/alone/*.spec.ts`, one at a time, English then Arabic | `ltr`, `rtl` |

Chat refuses while any training run is past `queued`, because they would share the memory, and
freeing the built-in engine unloads the model every other chat is using. So a journey that
trains, or takes the built-in engine away, goes in `journeys/alone/`, which runs after everything
else, one test at a time.

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
- **`shot(name)` saves a screenshot** for the release's reference artifact, of the test's page or
  of the page given as its second argument. Screenshots are kept for people to compare, never
  compared pixel by pixel.
- **Wait for what the page shows before acting on it.** A dialog is typed into once it has
  focused its first field (Material moves focus there when it has finished opening, and typing
  earlier can land in it), and a page is reloaded once the change it should keep has shown.
- **A new write endpoint goes in `VIEWER_WRITES`** (`harness/roles.data.ts`), with the answer a
  viewer gets, or `roles.spec.ts` fails: it sends every write the API schema lists as a viewer,
  and checks the list and the schema name the same operations.
- **Types live in `*.types.ts`**, as everywhere else (rule 30).

## Classes and methods

**`readStack()`** (`harness/stack.ts`) — the running stack from `stack.json`: addresses, data
folder, setup code, version, process ids. **`FRONTEND`**, **`BACKEND`**, **`RESULTS`**,
**`STACK_FILE`**, **`PORT`** — where things are, from `E2E_RESULTS`, `E2E_STACK` and `E2E_PORT`.

**`label()`**, **`contains()`**, **`anyValues()`**, **`text()`**, **`literal()`**,
**`startsWith()`**, **`stamp()`** (`harness/copy.ts`) — text and the patterns that find it:
- `label()` is a bundle string as a regular expression for an accessible name or a label. It is
  anchored, tolerates the bidi isolates the page puts around filled-in values, and tolerates a
  required field's asterisk.
- `contains()` is the same, unanchored.
- `anyValues()` matches one or more bundle strings whatever values fill them, for text whose
  values a journey does not know.
- `text()` is the filled-in string.
- `literal()` matches a value as it is written, and `startsWith()` matches text that begins with
  it, after any whitespace or bidi isolates.
- `stamp()` is a short number, different on every call, that makes a name a journey creates its
  own.

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

**`startConversation()`**, **`ask()`** (`harness/chat.ts`) — chat through the API:
`startConversation()` opens a conversation in a project, with a title if one is given, and `ask()`
sends a message and waits for the whole reply, failing if it does not finish.

**`versionsOf()`**, **`numbered()`**, **`versionTitle()`**, **`slugOf()`**, **`repoOf()`**
(`harness/versions.ts`) — what names a version or a model:
- `versionsOf()` reads a project's versions, and `numbered()` picks one by its number.
- `versionTitle()` is the title the page gives a version in a language, the seeded root under
  its translated name.
- `slugOf()` is the name a project is served under, and `repoOf()` a model's repository id.

**`SavedSession`**, **`withKey()`**, **`readJson()`**, **`answer()`**, **`writeOperations()`**
(`harness/access.ts`) — who the API lets in:
- `SavedSession` is a role's API session from its saved state; `send()` sends with the CSRF
  token, as a form when asked.
- `withKey()` is a request context that carries an API key instead of a session.
- `readJson()` reads a response as a JSON object, and `answer()` reads a refusal as its status
  and error code.
- `writeOperations()` lists every write in the API schema, each with a path a request can be sent
  to.

**`VIEWER_WRITES`** (`harness/roles.data.ts`) — the answer a viewer gets from each write
operation, by operation id.

**`choose()`**, **`pickFile()`**, **`signedOut()`**, **`settled()`**, **`horizontalOverflow()`**,
**`estimated()`** (`harness/pages.ts`) — what a page needs beyond a click:
- `choose()` opens a menu until its item shows, then picks it.
- `pickFile()` answers the file picker a button opens.
- `signedOut()` is a page in a new signed-out browser, in a language, recording its errors.
- `settled()` waits until nothing in the page is loading.
- `horizontalOverflow()` is how far the page is wider than the window.
- `estimated()` waits for the Architect's estimate of a design with that many layers.

**`test`**, **`expect`** (`harness/fixtures.ts`) — Playwright's, with:
- **Options:** `uiLocale` (the language the app opens in, set before the page loads; `null`
  leaves a first visit to choose) and `allowConsoleErrors`.
- **Values:** `locale` (the language in effect), `t` (`label()` in that language), `stack` and
  `world`.
- **Helpers:**
  - `owner`, the owner's `MesbahApi`;
  - `as(role)`, a page signed in as another role;
  - `shot(name, page?)`.
- **`consoleGuard`**, which fails a test whose page logged an error.

**`startIn()`**, **`recordErrors()`** (`harness/fixtures.ts`) — `startIn()` sets the language a
page opens in before it loads, and `recordErrors()` collects what a page logs as an error. The
fixtures use both, and so does `signedOut()`.

**`globalSetup()`** (`global-setup.ts`) — starts a stack with `tools.release.stack` unless
`E2E_STACK` names one, and stops it afterwards.
