# feature: chat (frontend)

`ChatPanel` — the correction workflow UI. Sessions rail + conversation + composer.

- Sessions rail: list/create/select sessions; per-session approved-example count badge.
- Conversation: user/assistant bubbles. Assistant replies are split by
  `core/think.ts::splitThink` into the `<think>` chain and the answer: the chain
  renders as a collapsed dimmed `<details>` ("سلسلة التفكير · thinking", plain text,
  never through the markdown pipe — the sanitizer would mangle the tags), the answer
  renders as **Markdown** (`MarkdownPipe` via `[innerHTML]`, Angular-sanitized).
  While a reply streams inside an unclosed `<think>`, the section is forced open
  with a "…يفكّر" pulse and collapses once `</think>` arrives.
  **Each assistant reply** has actions:
  - **تصحيح (edit)** → modal dialog. Thinking-model replies get **two tabs**
    (`p-tabs`): سلسلة التفكير · thinking first, الرد · response second — both
    editable; an emptied thinking tab auto-preserves the original chain. Answer-model
    replies get a single textarea. Save recombines via `joinThink` →
    `api.editMessage({content})` (marks corrected + approved; shows "معدّل" /
    "معتمد للتدريب" tags). The `<think>` block must survive corrections or the
    fine-tuned model stops thinking (backend re-attaches it as a safety net).
  - **تحسين ذاتي (self-correct / "magic wand")** → `api.selfCorrectStream` → the
    SAME model rewrites its own reply (SSE stream, replaces content in place). Marks
    **corrected but NOT approved** — pending human review — and shows a "تحسين ذاتي"
    tag (`meta.self_corrected`). The original draft is kept; a **عرض الأصل/المُحسّن**
    toggle (`showOriginalIds`) swaps between them.
  - **اعتماد (approve toggle)** → `api.editMessage({approved})`.
  - **إعادة توليد (regenerate)** on the last reply → `api.regenerate`.
- The editable per-session **correction prompt** lives behind the header's "تعليمات
  التحسين" button (`openCorrectionPrompt`/`saveCorrectionPrompt` → `updateSession
  ({correction_prompt})`); empty means the backend default is used.
- Composer: Enter sends (`api.chat`); a "…النموذج يكتب" placeholder shows while waiting.
- **503 handling**: if the ML runtime isn't installed, shows a friendly warn toast
  and reloads the session (keeps the user's message visible).

State is local `signal`s; `current()` holds the open session with its messages.
Helpers `append/replace/refreshList` keep the rail count in sync after edits.

To switch to token streaming, call the SSE endpoint
(`/api/sessions/{id}/chat/stream`) instead of `api.chat`.
