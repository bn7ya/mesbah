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
    In **Simple mode** (`core/ui-mode.ts`) this is the one plain-language "teach"
    action, labeled "علّم المساعد بردّ أفضل" — the backend already auto-approves
    on edit, so no separate approve step is needed.
  - **تحسين ذاتي (self-correct / "magic wand")** → `api.selfCorrectStream` → the
    SAME model rewrites its own reply (SSE stream, replaces content in place). Marks
    **corrected but NOT approved** — pending human review — and shows a "تحسين ذاتي"
    tag (`meta.self_corrected`). The original draft is kept; a **عرض الأصل/المُحسّن**
    toggle (`showOriginalIds`) swaps between them. **Expert mode only** — reviewing
    a model-generated rewrite before approving it isn't part of the beginner flow.
  - **اعتماد (approve toggle)** → `api.editMessage({approved})`. Relabeled
    "👍 استخدم هذا الرد للتدريب" / "تراجع" in Simple mode — same call;
    `include_in_training` already defaults `true` at message creation, so one tap
    is a complete training-inclusion action.
  - **إعادة توليد (regenerate)** on the last reply → `api.regenerate` (both modes).
- The editable per-session **correction prompt** lives behind the header's "تعليمات
  التحسين" button (`openCorrectionPrompt`/`saveCorrectionPrompt` → `updateSession
  ({correction_prompt})`); empty means the backend default is used. Like the
  system-prompt button and the raw model-version `p-select`, it's **Expert-mode
  only** — a Simple-mode session silently uses the project's active version (the
  backend default when `model_version_id` is unset).
- Composer: Enter sends (`api.chat`); a "…النموذج يكتب" placeholder shows while waiting.
- **503 handling**: if the ML runtime isn't installed, shows a friendly warn toast
  and reloads the session (keeps the user's message visible).

State is local `signal`s; `current()` holds the open session with its messages.
Helpers `append/replace/refreshList` keep the rail count in sync after edits.

To switch to token streaming, call the SSE endpoint
(`/api/sessions/{id}/chat/stream`) instead of `api.chat`.
