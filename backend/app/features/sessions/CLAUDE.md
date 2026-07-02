# feature: sessions (chat + corrections)

The product's core loop: **user asks → model answers → user edits the answer →
the edited turn becomes a training example.**

## Files
- `router.py` — sessions CRUD + chat. Routes at `/api/projects/{id}/sessions`,
  `/api/sessions/{id}`, `/api/messages/{id}`.
- `service.py` — message ordering, history, and the correction rules.
- `schemas.py` — `SessionRead` embeds messages + `approved_count`.

## Correction workflow (the important part)
- `edit_message`: on the **first** edit of an assistant reply, the model's draft is
  saved into `original_content`; `corrected=True` and `approved=True`
  (a human bothered to fix it → it's the target). See `service.edit_message`.
  **Thinking models**: if the previous content carried a `<think>…</think>` chain
  and the new content has none, the previous chain is re-attached
  (`core/think.py::split_think`/`join_think`) — training examples that lose the
  block teach the fine-tuned model to stop thinking. An explicit (even empty)
  `<think></think>` in the new content is respected as deliberate. Assistant-only.
- `apply_self_correction`: the **"magic wand"** — the model rewrites its OWN reply.
  Preserves `original_content` and flips `corrected` like `edit_message`, but
  **deliberately does NOT touch `approved`**: a self-correction is the model's own
  output, not a human quality signal, so it stays pending human review before it can
  become training data. Records provenance in `meta` (`self_corrected`,
  `correction_prompt`, `corrected_at`).
- `set_flags`: toggle `approved` / `include_in_training` without editing text.
- Only assistant turns that are `approved && include_in_training` count as training
  data (`approved_count`, and the training dataset builder).

## Self-correction endpoint
- `POST /messages/{id}/self-correct` → SSE token stream (same `token`/`done`/`error`
  vocabulary as `chat/stream`), then persists via `apply_self_correction`. Feeds the
  model its draft + the correction system prompt (per-call override → session
  `correction_prompt` → `settings.default_correction_prompt`) and asks it to rewrite.
  Session column `correction_prompt` is the editable per-session prompt.

## Chat endpoints
- `POST /sessions/{id}/chat` → adds the user turn, calls
  `inference.service.generate_reply`, persists the assistant turn. 503 if the ML
  runtime is missing.
- `POST /sessions/{id}/chat/stream` → SSE token stream, then persists.
- `POST /sessions/{id}/regenerate` → drops the last assistant turn, regenerates.

## Gotchas
- Deleting a session must delete its messages first (manual cascade in the router).
- The streaming endpoint persists the assembled reply with a **fresh** DB session
  (the generator outlives the request session).
