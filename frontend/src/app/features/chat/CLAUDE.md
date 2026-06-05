# feature: chat (frontend)

`ChatPanel` — the correction workflow UI. Sessions rail + conversation + composer.

- Sessions rail: list/create/select sessions; per-session approved-example count badge.
- Conversation: user/assistant bubbles. **Each assistant reply** has actions:
  - **تصحيح (edit)** → inline textarea → `api.editMessage({content})` (marks
    corrected + approved; shows "معدّل" / "معتمد للتدريب" tags).
  - **اعتماد (approve toggle)** → `api.editMessage({approved})`.
  - **إعادة توليد (regenerate)** on the last reply → `api.regenerate`.
- Composer: Enter sends (`api.chat`); a "…النموذج يكتب" placeholder shows while waiting.
- **503 handling**: if the ML runtime isn't installed, shows a friendly warn toast
  and reloads the session (keeps the user's message visible).

State is local `signal`s; `current()` holds the open session with its messages.
Helpers `append/replace/refreshList` keep the rail count in sync after edits.

To switch to token streaming, call the SSE endpoint
(`/api/sessions/{id}/chat/stream`) instead of `api.chat`.
