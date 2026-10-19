# features/serving

The Engines page: where Mesbah runs models, and how other tools reach them. Every signed-in user
sees it; trainers free the engine's memory and make API keys; administrators connect, change and
disconnect engines.

## Route and guard

`/engines`. `servingGuard` is `roleGuard('viewers')`; the backend enforces the real rule
(`ViewersReadAdminsWrite` on engines, `IsTrainer` on unloading and keys). The page hides what a
role may not do (`ServingStore.canManage`, `canTrain`). The menu lists it after Models.

## Backend counterpart

`backend/apps/serving/` — `GET|POST /api/serving/engines/`, `GET|PATCH|DELETE
/api/serving/engines/<id>/`, `POST /api/serving/engines/<id>/unload/`, `GET|POST
/api/serving/keys/`, `DELETE /api/serving/keys/<id>/`. `serving.types.ts` mirrors the serializers,
the page envelope included. The page also reads `GET /api/projects/?page_size=5` for a project's
slug to put in the examples.

## What the page shows

- **Mesbah's engine**: the built-in engine on an outlined card, running or not as an icon and
  words. Not running: the commands that start it (pip, Docker, Docker with a GPU), each with Copy.
  Running: the base model, the versions loaded (each linking to its project's Versions tab), what
  it runs on (the processor, or GPU n), whether the model is compressed to 4-bit, and a Busy
  marker. Trainers get Free memory (asks first); administrators get Make default while another
  engine is the default.
- **Other engines**: one card per connected engine: name, state, default and turned-off markers,
  the kind with its one-line explanation, address, model name, versions loaded. Administrators
  connect, edit, turn on and off, make default and disconnect (asks first). With none, a note says
  Mesbah's own engine is enough to start.
- **API keys** (trainers and above): a table with Material paginator; New key opens a dialog that
  shows the key once, with Copy; Revoke asks first. Viewers and reviewers see a short note.
- **Use from other tools**: the OpenAI- and Ollama-compatible addresses from the page's own
  origin, and a Python and a curl example for each, naming the first project's slug and the
  placeholder key `msb_…`. Visible to everyone.

## Classes and methods

**`ServingApi`** (`data/serving.api.ts`) — one method per endpoint above, and `exampleSlugs()` for
the projects list.

**`deviceOf()`** (`data/device.ts`) — reads the engine's device string into the processor, GPU n,
another device or none.

**`ServingStore`** (`state/serving.store.ts`), provided by the route — `engines`, `loading`,
`loaded`, `error`, `working` (ids mid-request), `saving` and, for keys, `keys`, `keysPageIndex`,
`keysPageSize`, `keysLoading`, `keysError`, `keyWorking` and `creatingKey` as signals.
- `builtin`, `others` (default first), `canManage`, `canTrain` and `exampleSlug` are `computed`.
- `visit()` clears and reloads everything when the page opens; `load()` fetches the engines.
- `watch()` is a stream the page subscribes to: every five seconds it refreshes the engines
  quietly. An answer asked for before a change landed is dropped, so a slow refresh never undoes a
  toggle.
- `connect()` and `save()` hand a refusal back to the dialog; `change()`, `unload()` and
  `disconnect()` change one engine and keep a failure in `error`.
- `loadKeys()`, `createKey()` and `revokeKey()` do the same for keys. `createKey()` returns the
  key to the dialog and keeps it nowhere else.

**`EnginesPage`** (`pages/engines/`) — header, the failure alert with Try again, and the four
sections. Loads through the store and subscribes to `watch()` until it is destroyed.

**`BuiltinEngine`**, **`OtherEngines`**, **`ApiKeys`**, **`ConnectGuide`** (`components/`) — one
section each; they read the route's store, open dialogs with their own injector, ask before
freeing memory, disconnecting or revoking, and report each change in a snack bar. `guideFor()`
(`components/connect-guide/snippets.ts`) builds the addresses and examples.

**`LoadedVersions`** — the versions on an engine, each linking to its project's Versions tab.
**`CopyButton`** — copies a text through the CDK clipboard and reports in a snack bar. It sits
inside the shared `<app-code-block>` (the address, each example, each start command), which sets
the code in its own block.

**`EngineFormDialog`** (`dialogs/engine-form/`) — connects an engine or edits one. The kind is a
select with its explanation under it and cannot change once connected; the model name shows only
for llama.cpp and OpenAI-compatible servers. When editing, an empty API key keeps the saved one
and Remove the key sends an empty one on save; only changed fields are sent, and nothing is sent
when nothing changed.

**`NewKeyDialog`** (`dialogs/new-key/`) — asks a name, then shows the key once in a read-only
field with Copy. The key field takes focus with its text selected and the dialog can only be
closed with Done.

**`servingGuard`** (`guards/`) — viewers and above.

## Errors

`errors.builtin_engine_kept`, `engine_unreachable`, `engine_timeout`, `engine_rejected_token`,
`engine_failed` and `no_engine` are in this bundle; the interceptor swaps them in for the server's
English message.

## Decisions worth not re-litigating

**Polling is a stream the page owns.** Leaving the page cancels the timer and any request in
flight. A failed refresh keeps the last state and shows nothing.

**Turn on and off is a button, not a switch.** A switch flips before the request answers and has to
be put back when it fails; a button states the action and the card shows the result.

**The built-in engine has no Disconnect, no Edit and no on/off.** It can only be made the default;
the backend keeps `409 builtin_engine_kept` as the real guard.

**Code is left to right, in the monospace stack, and scrolls inside itself.** `<app-code-block>`
(shared) sets code in `--app-font-mono`, the stack `code` uses everywhere, and keeps each line
whole: a long command scrolls sideways inside its block, so it is copied and read as it will be
typed, and never widens the page.

**An engine card keeps its four actions on one line.** The grid of engine cards starts a column at
36rem so Edit, Turn off, Make default and Disconnect fit beside each other; under the `sm`
breakpoint they sit in two columns of two.
