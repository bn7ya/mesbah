# features/chat

The Chat tab of a project: talk to one of its versions, and correct what it says. A wrong reply
is edited in place, the way a sent message is edited, and its thinking chain is edited on its
own. An edited or approved reply becomes training data. Every signed-in user reads conversations;
reviewers and above write, correct and approve.

## Route and guard

`/projects/:projectId/chat` and `/projects/:projectId/chat/:conversationId`, children of the
project frame. The app declares the tab in `app.routes.ts` through `projectFrame()`, and
`PROJECT_TABS` lists it; this feature never imports `projects`. **One route config handles both
URLs** through `conversationMatcher`, so moving between conversations reuses the page instead of
rebuilding it. `chatGuard` is `roleGuard('viewers')`; the backend enforces the real rule
(`ViewersReadReviewersWrite`, `IsReviewer` on reply, restore and approve), and the page hides
the composer, the menu, rename and remove from viewers.

## Backend counterpart

`backend/apps/chat/` — `GET|POST /api/chat/`, `GET|PATCH|DELETE /api/chat/<id>/`,
`GET /api/chat/<id>/messages/`, `POST /api/chat/<id>/reply/` (`text/event-stream`),
`GET|PATCH /api/chat/messages/<id>/`, `POST .../restore/` and `.../approve/`. `chat.types.ts`
mirrors the serializers, the page envelope included. Three reads belong to other apps, the only
places this feature touches them: `GET /api/projects/<id>/` (the project's instructions and reply
settings, shown as what a conversation follows, and whether its base model can think), `GET /api/versions/?project=` (the version
select, and a version's number for the footer of a reply) and `GET /api/serving/engines/` (the
engine select, only the ones that are on). The error codes the engine and the corrections can
answer with have `errors.*` entries in this bundle, and `glossary.approved` lives here too.

## What the page shows

A `mat-sidenav-container`: the conversations on the inline-start side on wide screens, and a
drawer opened from the header on narrow ones. The open conversation fills the rest.

- **List**: title (or "New conversation"), when it was last changed and its message count; New
  conversation and a remove button per row (reviewers and above; removing asks first); Show more
  when the server has more pages. An empty list says what chatting is for here.
- **Header**: the title, renamed in place; the version that answers (`mat-select`: the active
  version, or any version); the engine (hidden when only one is on); the Thinking switch; and a
  Settings dialog with this conversation's instructions (the project's shown beneath the field)
  and the three reply settings, each falling back to the project's. Viewers see the same facts
  as text.
- **Messages**: chat bubbles, the reader's own at the inline-end and the model's at the
  inline-start, each text in its own direction (`dir="auto"`, `pre-wrap`). A reply carries its
  thinking chain above it in a collapsible section (open while it streams, closed once done), and
  a footer: the version that answered, the time, and marks for approved, edited, thinking edited,
  stopped, failed and not used for training, each an icon and a word. A failed reply says why
  (`errors.<code>`), with a link to Engines when the engine is not running. Expert mode adds the
  engine, tokens and duration. The menu (reviewers and above): Edit reply, Edit or Add thinking,
  Approve as it is or Withdraw approval, Used for training, Restore the model's reply or thinking
  (only when edited, asks first), Copy. A reply with no text and no thinking (stopped while the
  model was loading) says "Stopped before the model wrote anything", and its menu offers neither
  Approve nor Used for training; a server refusal (`409 empty_reply`) reads the same in
  `errors.empty_reply`.
- **Editing**: the text turns into a `mat-form-field` textarea in the bubble with Save and
  Cancel. Escape cancels, Ctrl or Command with Enter saves, a blank reply is refused. "Show what
  the model wrote" reveals the original beside the draft. Focus goes to the editor when it opens
  and back to the bubble when it closes.
- **Composer**: Enter sends, Shift with Enter adds a line, Send becomes Stop while a reply
  streams, and focus returns to the field after sending. Viewers see one line saying they can
  only read.
- **Streaming**: the reply is read through `HttpClient` as `text/event-stream`, so the CSRF and
  error interceptors apply. "Loading the model…" shows from the first event until the engine is
  ready, then "Thinking…" or "Writing…" while text arrives; the view stays at the bottom until the
  reader scrolls up, and a button brings it back.

## Classes and methods

**`ChatApi`** (`data/chat.api.ts`) — one method per endpoint above, and the three reads of other
apps. `reply()` posts the question with progress reporting on and a text body, and turns every
`HttpDownloadProgressEvent` into the new reply events it holds, reading only what it has not read
yet; the final response catches up on anything left. `engines()` keeps the ones that are on.

**`parseFrames()`**, **`toReplyEvent()`** (`data/sse.ts`) — the server-sent-event reader, pure.
`parseFrames()` takes the text received so far and an offset and returns the complete events after
it, with the new offset: a half-received event waits for the rest, comment lines (keepalives) and
events without data are skipped, several `data:` lines join with a line break, and `\n`, `\r\n`
and `\r` all end a line. `toReplyEvent()` turns a frame into a `start`, `ready`, `thinking`,
`content`, `done` or `error` event, and ignores what it does not know.

**`ConversationsStore`** (`state/conversations.store.ts`), provided by the route — the project's
conversations and what the header needs of the project.
- `items`, `nextPage`, `loading`, `error`, `creating` and `removing` are signals; `defaults` (the
  project's instructions and reply settings), `versions`, `activeVersion` and `engines` are
  `computed` over three resources keyed by project id; `canWrite` is reviewers and above.
- `open()` points the store at a project and loads the first page, reloading when it is the open
  one, since route stores outlive their page; `reload()` and `more()` ask again and for the next
  page.
- `create()` starts a conversation and puts it first; `remove()` removes one. Both hand a refusal
  back. `replace()` takes a changed conversation, keeps its message count when the server leaves
  it out, and sorts the list newest first.

**`ConversationStore`** (`state/conversation.store.ts`), provided by the route — the open
conversation, its messages, and the reply being written.
- `conversation`, `messages`, `loading`, `ready` and `error` come from two resources keyed by
  conversation id; the messages load every page, oldest first.
- `stream` holds the live text of the reply being written (`replyId`, `phase`, `thinking`,
  `content`, `engine`), and `sending` is true from the click until the reply is saved. The
  message in `messages` stays the saved placeholder until `done`, so only the bubble that is
  writing re-renders as text arrives.
- `open()` points the store at a conversation, or at none, and stops a reply that is still
  streaming for the one before. `leave()` does the same when the page is destroyed: leaving the
  conversation stops the reply, and the server keeps what arrived.
- `send()` posts the question and resolves `true` at the first event, `false` when it was refused
  or stopped before the server answered; a refusal is kept in `sendError`. `start` appends both
  saved messages at once, `done` and `error` replace the reply with the saved one, and the
  conversation is read again for its new title.
- `stop()` unsubscribes, which aborts the request, marks the reply stopped with the text that
  arrived, and loads the saved reply, asking again until the server has saved it. A dropped
  connection takes the same path.
- `edit()`, `restore()`, `approve()` send `seen` with the reply's `updated_at` and replace the
  reply with the answer; each reports success as `null` or hands the refusal back. A
  `message_changed` refusal also reloads that reply. `change()` saves the conversation's title,
  version, engine, thinking, instructions or reply settings.
- `versionLabel()` names the version that answered from the project's versions, with its number.
- An `effect` publishes the open conversation, with the count of the messages that are loaded,
  to `ConversationsStore.replace()` whenever either changes, so the list's "Messages: n" follows a
  send the moment the reply starts and a reply that is saved or stopped, without a reload.

**`ChatPage`** (`pages/chat/`) — the sidenav layout. Opens the project and the conversation from
its two inputs, stops the reply when destroyed, and shows what to do when no conversation is open
or the one asked for is not found.

**`ConversationList`** (`components/conversation-list/`) — the list, its empty and failed states,
New conversation, remove (with a confirmation) and Show more.

**`ConversationHeader`** (`components/conversation-header/`) — the title and its rename, the
version and engine selects, the Thinking switch and the Settings button. Each control follows its
own `linkedSignal`, so a refused change puts the control back as it was.

**`MessageList`** (`components/message-list/`) — the messages in a scrollable region. Stays at the
bottom while the reader has not scrolled up, watching the DOM for growth (`cdkObserveContent`) so
new messages, streamed text and an editor opening all keep their place; shows a button to jump to
the latest.

**`MessageBubble`** (`components/message-bubble/`) — one message: the thinking section, the text,
the status line for a reply in progress or failed, the footer with its marks and the menu. Holds
the editing state (which part, and the text it started from) and reports each action in a snack
bar.

**`MessageEditor`** (`components/message-editor/`) — the in-place editor for a reply or a
thinking chain, with Save, Cancel and the original on request.

**`ThinkingSection`** (`components/thinking-section/`) — the collapsible thinking chain: open
while a reply streams or is edited, closed once done, and left open after an edit.

**`Composer`** (`components/composer/`) — the message field and Send or Stop.

**`ConversationSettings`** (`dialogs/conversation-settings/`) — instructions and the three reply
settings, each a value or "follows the project". Opened with the page's injector, so it shares
the route's stores.

**`chatGuard`** (`guards/`) — viewers and above. **`conversationMatcher`** (`chat.routes.ts`) —
matches `chat` and `chat/:conversationId` as one route.

## Decisions worth not re-litigating

**The stream is read through `HttpClient`.** The fetch backend is Angular's default, and
`reportProgress` with a text body hands over `partialText`, so the CSRF and error interceptors
still run. The reply is sent without an `Accept: text/event-stream` header, which DRF would
refuse with `406`. `errorInterceptor` reads an error body that arrives as text.

**Stopping is unsubscribing.** The server saves what arrived as `stopped`; the store then asks for
that message until it is no longer `streaming`.

**The live text is not in `messages`.** Appending a token to an array of messages would
re-render every bubble; a separate `stream` signal re-renders one.

**A correction approves the reply, a restore does not.** That is the backend's rule, and the page
shows the mark it answers with.

**An edit keeps the reader's text on a conflict.** On `message_changed` the reply is reloaded and
the editor keeps what was typed, so saving again replaces the other change on purpose.

**Restoring asks first.** It discards a person's correction.

**The Thinking switch follows the base model, as the project's does.** `ChatApi.project()` reads
`base_model.supports_thinking` into `ProjectDefaults`; when it is `false` the switch is disabled
and the reason sits beside it. While the project is still loading nothing is judged, so the switch
stays on offer.
