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
- `set_flags`: toggle `approved` / `include_in_training` without editing text.
- Only assistant turns that are `approved && include_in_training` count as training
  data (`approved_count`, and the training dataset builder).

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
