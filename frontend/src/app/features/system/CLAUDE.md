# features/system

The System page: what this machine offers for training and chat, in plain terms. Every
signed-in user sees it; administrators choose the GPUs and save the HuggingFace token.

## Route and guard

`/system`, the start page after signing in. `systemGuard` lets any signed-in user in; the
backend decides who may change anything (`CanManageSystem`), and the page hides the controls
from everyone else (`SystemStore.canManage`).

## Backend counterpart

`backend/apps/system/` — `GET /api/system/`, `PUT /api/system/gpus/`,
`PUT|DELETE /api/system/huggingface-token/`. `SystemOverview` mirrors the overview serializer.

## What the page shows

- **GPUs**: none found (with what that means), or the VRAM Mesbah can use, how the GPUs were
  chosen, and for an administrator a selection list to change it.
- **Memory and storage**: RAM, CPU cores, a disk-space meter; Expert mode adds the OS, Python
  and the data folder.
- **HuggingFace account**: whether a token is saved, for which account, and the form.
- **Training parts**: ready, or the install command; a warning when a GPU is present but the
  installed torch is a CPU build; Expert mode lists every part and its version.

## Classes and methods

**`SystemApi`** (`data/system.api.ts`) — one method per endpoint above.

**`SystemStore`** (`state/system.store.ts`), provided by the route — the overview, `loading`,
`saving` and the last `error` as signals.
- `canManage`, `gpus`, `selectedGpus`, `trainingReady`, `torchWithoutCuda` are `computed` from
  the overview and the signed-in user.
- `load()` fetches the overview; `selectGpus()`, `saveHuggingFaceToken()` and
  `removeHuggingFaceToken()` send a change and keep the overview the server answers with,
  reporting success.

**`SystemPage`** (`pages/system/`) — the page above. Keeps the GPU choice in a
`linkedSignal` until it is saved, validates the token field through an `ErrorStateMatcher`,
asks before removing the token, and reports a saved change in a snack bar.

**`systemGuard`** (`guards/`) — any signed-in user.

## Decisions worth not re-litigating

**Sizes are binary and labelled GB**, the way an operating system shows a 16 GB card.

**The token field never shows the saved token.** It is write-only on the backend; the page
shows the account and the last four characters.
