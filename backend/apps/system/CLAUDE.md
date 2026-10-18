# apps/system

What this machine can do, and the few install-wide settings that follow from it: which GPUs
Mesbah uses and the HuggingFace token. The backend half of the System page.

## Its counterpart

`frontend/src/app/features/system/` — the System page.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/system/` | signed in | the overview |
| `PUT` | `/api/system/gpus/` | administrator | the overview; `{"gpus": []}` goes back to automatic |
| `PUT` | `/api/system/huggingface-token/` | administrator | the overview; `400 hf_token_rejected`, `503 hf_unreachable` |
| `DELETE` | `/api/system/huggingface-token/` | administrator | the overview |

The overview — mirrored by `SystemOverview` in `features/system/data/system.types.ts`:
`machine` (GPUs with memory in bytes, driver, RAM, CPU count, OS, Python), `selected_gpus`,
`gpu_choice` (`automatic` or `chosen`), `usable_vram_bytes` (sum over the selected GPUs),
`storage` (the data folder and its disk), `parts` (optional packages and their versions)
and `huggingface` (`configured`, the last four characters, the account name). No list
endpoint, so rule 17 does not apply.

## Layers

```
views.py → services/system_service.py → repositories/{setting,secret}_repository.py → Setting / Secret
                     └→ mesbah.hardware, mesbah.parts (probes, no Django)
```

## Classes and methods

**`Setting`** — one install-wide value under a unique key (`selected_gpus`). **`Secret`** — one
encrypted value under a unique name (`huggingface_token`), with a four-character hint and the
account it belongs to.

**`SettingRepository`** / **`SecretRepository`** — find by key or name, and `put()`, which
updates the live row or creates one.

**`SecretBox`** (`services/secret_box.py`) — seals and opens secrets with a key derived from
`SECRET_KEY`. A secret sealed under another key opens to `None`, which reads as "not saved".

**`SystemService`** (`services/system_service.py`), for the acting user:
- `overview()` — the machine, the effective GPU choice, storage, parts and token status.
- `select_gpus()` — stores the chosen indices; refuses one the machine does not have.
- `save_huggingface_token()` — asks HuggingFace who the token belongs to, then seals it.
- `remove_huggingface_token()` — soft-deletes the secret.

**Errors** (`services/errors.py`) — `HuggingFaceTokenRejected`, `HuggingFaceUnreachable`,
`UnknownGpu`: each a stable `code` the frontend translates.

**`CanManageSystem`** (`permissions.py`) — who may change the system. **`SystemView`**,
**`GpuSelectionView`**, **`HuggingFaceTokenView`** — the endpoints above.

## Decisions worth not re-litigating

**The token is never returned.** Only its last four characters and the account name. It is
checked with HuggingFace before it is stored, so a typo fails at the form, not at a download.

**The automatic choice is the largest GPU**, and nothing is stored for it. An empty choice
deletes the preference rather than storing "all", so a new card added later is not silently
used.

**The probe never imports torch.** NVML first, then `nvidia-smi`; the web process stays light
and the answer is the same whether or not the training parts are installed.
