# features/architect

The Model designer page (`/architect`): design a new model (a decoder, a mixture of experts or an encoder-decoder),
see what it adds up to, save it, and train it from nothing on the approved replies of other
projects and on library datasets. Every signed-in user sees and uses the designer; trainers and
above save, rename, remove and train.

## Route and guard

`/architect`. `architectGuard` is `roleGuard('viewers')`; the backend enforces the real rule
(`IsViewer` to read and estimate, `IsTrainer` to save, remove and train). The page hides Save,
Train, Rename and Remove from viewers and reviewers (`ArchitectStore.canWrite`). The menu lists it
after Models.

## Backend counterpart

`backend/apps/architect/`, mounted at `/api/architect/`: `GET presets/`, `POST estimate/`, drafts
CRUD at `drafts/` and `drafts/<id>/`, `POST drafts/<id>/train/`. The train dialog also reads
`GET /api/projects/`, `GET /api/training/plan/?project=` (its `corrections`) and `GET /api/datasets/`.
`architect.types.ts` mirrors the serializers; the api maps wire to domain (below). `estimate/` takes the
designer's tokenizer next to the design; when it names a library model with a larger vocabulary the
answer's counts and memory use that size and it carries `tokenizer_vocabulary` (`null` when the library
does not know the tokenizer), while its `design` stays as it was sent. A saved design's own answer is
counted the same way.

## What the page shows

- **Start from**: the ready-made designs as cards (name in words, kind, parameters, and the
  parameters each token uses for a mixture of experts) and the saved designs as rows (open, rename,
  remove). Choosing one loads it into the designer and moves focus there.
- **Design**: a header with what the designer holds (a ready-made design, a saved design, with
  "Unsaved changes" when it differs, or a new one) and Save / Train model. Under it two panels:
  - the **designer**: the kind of model as a toggle with one sentence each, then only the fields
    that kind uses, grouped (shape, attention, feed-forward or experts, vocabulary and context,
    tokenizer, training step). Each field has its range and a plain hint; a refused field shows the
    reason in its `mat-error`. When the tokenizer is in the library and its vocabulary is larger than
    the number typed, a note under the vocabulary fields names the tokenizer and its size and says the
    model is counted with it; the typed number stays in the field.
  - **Size and memory**: the parameter total large, what each token uses (mixture of experts), a
    bar and legend of where the parameters are, the note when the vocabulary is most of the model,
    then two panels, one per optimizer (AdamW and 8-bit Adam): memory needed, whether it fits this
    machine as an icon and a word, and what it is made of. Wide screens put the two columns side
    by side.
- **Train dialog**: the new project's name; two lists, other projects' approved replies (a project
  with none is disabled, saying so) and ready library datasets, each chosen dataset with an optional
  row limit; the honest note that training from nothing needs far more examples than customising a
  model. Train stays disabled, with the reason beside it, until one project or dataset is chosen.
  When nothing is available, one line points to `/datasets`. Success goes to
  `/projects/<project>/training/<run>`.

## Classes and methods

**`ArchitectApi`** (`data/architect.api.ts`) — one method per endpoint, mapping wire to domain.
`presets()` returns blueprints, `estimate()` takes a request (design, sequence length, batch and
tokenizer), `drafts()` pages saved designs,
`createDraft()` and `changeDraft()` take a `Blueprint` (a change with `null` sends only name and
notes), `removeDraft()`, `train()`, and for the dialog `projects()`, `corrections()` (a project's
approved replies) and `datasets()` (only those with status `ready`).

**`Blueprint`** (`data/architect.types.ts`) — the editor's state: the kind, every field of every kind
(an empty field is `null`), the tokenizer, sequence length and batch. Fields a kind does not use keep
a default so switching kind does not lose them. `LIMITS` mirrors `mesbah.architect.LIMITS`;
`FIELDS`, `GROUPS` and `PARTS` say what the designer and the legend render.

**`blueprint.ts`** (`data/`) — pure helpers: `designRequest()` sends only the fields a kind uses
(an encoder-decoder always shares its vocabulary table), `estimateRequest()` adds the trimmed
tokenizer and is `null` while the sequence length or batch is outside its range,
`raisedVocabulary()` says whether an answer counted a larger vocabulary than the one sent (the
tokenizer's name and size, else `null`), `blueprintOf()` turns a wire design back into a
blueprint, `signature()` compares two blueprints ignoring unused fields, `withinLimit()`.

**`ArchitectStore`** (`state/architect.store.ts`), provided by the route:
- Editor: `blueprint`, `draft` (the saved design open in the designer), `startedFrom` (a
  ready-made design), `dirty` and `family` (`computed`).
- Estimate: `estimate`, `estimating` and `refusal` as signals. A change to the blueprint, the
  tokenizer included, is debounced 400 ms (`toObservable` + `debounceTime`), then `POST estimate/`; a
  refusal clears `estimate`. `vocabularyNote` (`computed`) is the sentence about a raised vocabulary,
  in the reader's language, from the request and answer that produced the numbers on screen, or `null`.
  It never changes `blueprint`: the form keeps what was typed. `fieldErrors` names the field of a refused design in the reader's language (the
  allowed range for `design_out_of_range`, a specific sentence for the key-value heads) and adds
  the local range checks of sequence length and batch; `refusalSummary` is a refusal naming no
  field.
- Permissions and gates: `canWrite`, `canSave`, `trainBlocker` (a translation key: nothing saved,
  unsaved changes, no tokenizer) and `canTrain`.
- Lists: `presets` (an `rxResource`), `draftPage` with `pageIndex`, `pageSize`, `draftsLoading`
  and `draftsError`, `working` (draft ids mid-request).
- Dialog data: `sources` (projects with their approved-reply counts, `null` when a count failed),
  `datasets`, `sourcesLoading`, `sourcesError`, `saving`, `training`.
- Methods: `setFamily()`, `setNumber()`, `setTokenizer()`, `setTied()`, `estimateAgain()`,
  `presetLabel()`, `usePreset()` (keeps the reader's tokenizer and sizing), `openDraft()`,
  `visit()` and `loadDrafts()`, `save()` (creates, or changes the open draft; the draft keeps the blueprint that was sent),
  `rename()` (keeps the open draft's blueprint),
  `removeDraft()`, `loadSources()` (projects and datasets together, plan counts six at a time) and
  `train()`. Saving, renaming and training hand a refusal back to the dialog instead of keeping it.

**`ArchitectPage`** (`pages/architect/`) — the page above. Opens the save and train dialogs with
its own injector, moves focus to the designer heading when a design is chosen, reports in snack bars
and goes to the new run after training starts. Its sections are `h2`s (Start from, Design); the
form's groups and the results card's title are `h3`s, and the breakdown's and the memory's titles
`h4`s.

**`StartingPoints`** (`components/starting-points/`) — the ready-made designs and the saved designs.
Asks before replacing a designer with unsaved changes, opens the rename dialog, asks before removing.
The two lists are named by a caption, not a heading, so each design's name (`h3`) stays the largest
thing in its card.

**`DesignerForm`** (`components/designer-form/`) — the kind toggle and the fields of the current
kind from `GROUPS` and `FIELDS`. A field's error state reads `ArchitectStore.fieldErrors` through an
`ErrorStateMatcher`. Shows `ArchitectStore.vocabularyNote` under the vocabulary fields.

**`Breakdown`** (`components/breakdown/`) — the parameter total, what each token uses, the bar and the
legend with a term button per part, and the note when the vocabulary is most of the model. **`TrainingMemory`**
(`components/memory/`) — the two optimizer panels and the GPU line, which says there is no GPU when no
GPU memory is available (`available_bytes` is 0), whatever the verdict is.

**`SaveDraftDialog`** (`dialogs/save-draft/`) — name and notes; saves the designer's design or only
renames, by the dialog's mode. **`TrainDialog`** (`dialogs/train/`) — the train form described above.

**`architectGuard`** (`guards/`) — viewers and above.

## Errors

`errors.design_*`, `errors.tokenizer_needed`, `errors.nothing_to_learn` and
`errors.dataset_not_ready` are in this bundle, so the error interceptor puts them in the reader's
language. The bundle also carries the glossary entries only this page uses
(`glossary.experts`, `.embeddings`, `.router`, `.tokenizer`, `.optimizer` and the rest), which
`<app-term>` finds once the route has registered it; `attention`, `feed_forward`, `moe`,
`parameters`, `token` and `vram` are the core bundle's.

## Decisions worth not re-litigating

**Train needs a saved design that matches the screen.** The backend trains the saved draft, not the
editor, so the button is off while the designer has unsaved changes.

**A refused design hides the numbers.** While estimating, the last numbers stay (the panel is
marked busy); once refused, they go, because they would describe a different design.

**The estimate counts the tokenizer's vocabulary, and the form does not.** Training raises a smaller
vocabulary to the tokenizer's, so the backend counts the design at that size when the library knows the
tokenizer. The page says so beside the vocabulary fields and leaves the typed number alone. For a
tokenizer the library does not know the field's hint says a smaller number is raised during training,
and the counts may be low.

**The note belongs to the answer on screen.** It is worked out when an answer settles, from the
request that produced it, so while a new estimate is pending it still describes the numbers shown.

**Counts follow `label: n`.** "Parameters: 2.2M", never "2.2M parameters".
