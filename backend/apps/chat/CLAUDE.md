# apps/chat

Conversations with a project's version, and their messages. A reply streams from the engine as
server-sent events (ADR-006) and is saved once, at the end — or as far as it got, when the
reader stops it. The backend half of the Chat page.

## Its counterpart

`frontend/src/app/features/chat/` — the Chat page.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/chat/?project=<id>` | viewer | a page of the project's conversations, newest first |
| `POST` | `/api/chat/` | reviewer | `201` a conversation; without `version` it follows the active version |
| `GET` | `/api/chat/<id>/` | viewer | one conversation |
| `PATCH` | `/api/chat/<id>/` | reviewer | title, version, engine, prompt, thinking, reply settings |
| `DELETE` | `/api/chat/<id>/` | reviewer | `204` |
| `GET` | `/api/chat/<id>/messages/` | viewer | a page of messages, oldest first |
| `POST` | `/api/chat/<id>/reply/` | reviewer | `text/event-stream` |
| `GET` | `/api/chat/messages/<id>/` | viewer | one message |
| `PATCH` | `/api/chat/messages/<id>/` | reviewer | the reply corrected: `content`, `thinking`, `include_in_training`, with `seen`; `409 message_changed`, `409 not_editable` |
| `POST` | `/api/chat/messages/<id>/restore/` | reviewer | the reply with one `part` (`content` or `thinking`) as the model wrote it |
| `POST` | `/api/chat/messages/<id>/approve/` | reviewer | the reply marked right as it is, or the mark taken back |

The stream: `start` (`asked` and `reply`, both saved), `ready` (`engine`), `thinking` and
`content` (`text`), then `done` (`reply`) or `error` (`code`, `message`, `reply`). A comment line
(`: keepalive`) goes out every ten seconds of silence, while a model loads or thinks.

## Layers

```
views.py → services/conversation_service.py → repositories/{conversation,message}_repository.py
         → services/reply_service.py ─→ apps.serving DeploymentService + EngineClient
         → services/message_service.py → repositories/message_repository.py
```

## Classes and methods

**`Conversation`** — a project's conversation: a title (the first message when none is given),
an optional pinned version and engine (else the active version on the default engine), and its
own prompt, thinking switch and reply settings over the
project's. **`Message`** — one turn: position, role, status (`streaming`, `complete`, `stopped`,
`failed`), the content and the thinking chain in separate fields with their originals and edit
times, the version and engine that answered, the finish reason or error code, token counts,
latency, and whether it is approved and used for training.

**`ConversationRepository`** — a project's conversations with their message counts, one locked
for a new turn, one with its project loaded. **`MessageRepository`** — a conversation's messages,
its history for the engine (failed and unfinished replies left out), one locked for a
correction, the next position.

**`ConversationService`** — `listing()`, `find()`, `describe()`, `create()`, `change()` (a version
must belong to the project, an engine must be on), `remove()`, `messages_of()`. **`describe_message()`** — a message as
the API shows it.

**`ReplyService`**:
- `begin()` — in one transaction: saves the user's message and an empty `streaming` reply, names
  the conversation, and builds the engine request (the prompt, the history with each reply's
  thinking as `reasoning_content`, the reply settings, `enable_thinking`).
- `stream()` — the event stream. A task loads the version (`DeploymentService.target()`) and
  reads the engine into a queue; the stream drains it, sending keepalives while it waits, and
  saves the reply when the engine finishes, fails, or the reader leaves.
**`Turn`** — one question and its reply in progress. **`Draft`** — what has arrived so far.

**`MessageService`** — corrections, like editing a sent message:
- `edit()` — replaces a reply's text, its thinking chain, or both; the first correction keeps the
  original, a correction back to the original clears the mark, and any correction approves the
  reply. `seen` must match the reply's `updated_at`, so two people never overwrite each other.
  A reply can gain a thinking chain it never had.
- `restore()` — puts one part back as the model wrote it; `approve()` marks a reply right as
  it is, or takes the mark back. Only an assistant reply that is not still streaming qualifies.

**`NoVersion`**, **`MessageChanged`**, **`NotEditable`** (`services/errors.py`) — the refusals.

## Decisions worth not re-litigating

**The view is sync and the stream is async.** DRF authenticates and validates in the sync view;
the reply is an async generator under ASGI, so a slow model holds no worker thread.

**A stopped reply is kept.** Closing the stream cancels the generator; it saves what arrived as
`stopped` under `asyncio.shield`, because a half answer is still something to correct.

**The thinking chain is its own field, never inside `content`.** It is edited, approved and
trained on separately, and the engine gets it back as `reasoning_content`.
