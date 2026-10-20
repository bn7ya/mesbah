# apps/architect

Designing a new model before training it from nothing: a dense decoder, a mixture-of-experts
decoder or an encoder-decoder. Every number on the page — parameters by part, what a token
uses, the memory to train it here — comes from `mesbah.architect`, which counts exactly as the
transformers implementations do. The backend half of the Architect page.

## Its counterpart

`frontend/src/app/features/architect/` — the Architect page.

## Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| `GET` | `/api/architect/presets/` | viewer | `{"presets": [...]}`: named starting points with their counts |
| `POST` | `/api/architect/estimate/` | viewer | counts, memory and fit for a design, a sequence length, a batch and an optional tokenizer; `400 design_<reason>` naming the field |
| `GET` | `/api/architect/drafts/` | viewer | a page of saved designs, each with its estimate |
| `POST` | `/api/architect/drafts/` | trainer | `201` a saved design |
| `GET` | `/api/architect/drafts/<id>/` | viewer | one design |
| `PATCH` | `/api/architect/drafts/<id>/` | trainer | the design changed |
| `DELETE` | `/api/architect/drafts/<id>/` | trainer | `204` |
| `POST` | `/api/architect/drafts/<id>/train/` | trainer | `202` `{project, run}`: a new project and its pretrain run, learning from the approved replies of `corrections_from` and from `datasets`; `400 tokenizer_needed`, `409 nothing_to_learn`, `409 dataset_not_ready` |

## Layers

```
views.py → services/architect_service.py → repositories/draft_repository.py → ArchitectureDraft
                                         └→ mesbah.architect (Design, count, memory, presets)
```

## Classes and methods

**`ArchitectureDraft`** — a saved design: a name and notes, the design as `mesbah.architect`
reads it, the tokenizer it will reuse, and the sequence length and batch it is sized for.

**`DraftRepository`** — drafts, most recently changed first.

**`ArchitectService`**, for the acting user:
- `presets()` — the starting points with their counts.
- `estimate()` — a design's counts, memory and fit against the GPUs chosen on the System page
  (with none, against the machine's RAM: `cpu_only` or `too_large`), and the note when the vocabulary is most of the model; counted at the tokenizer's vocabulary
  when that is larger (`tokenizer_vocabulary()`: the size a library model's config gives, else
  unknown), since training grows the model to it. The design comes back as it was given.
- `listing()`, `find()`, `describe()` (a draft with its estimate), `create()` and `change()`
  (both store the design as it was checked), `remove()`.
- `train()` — a scratch project named for the new model (`ProjectService.create_scratch()`) and
  its pretrain run (`TrainingService.create_pretrain()`), in one transaction.
**`design_of()`** — a design from JSON, or `DesignRefused`.

**`DesignRefused`** (`services/errors.py`) — `400 design_<reason>` with the field it is about:
`missing`, `invalid`, `out_of_range`, `not_divisible`, `odd_head_dim`,
`too_many_active_experts`, `tied_only`. **`TokenizerNeeded`** — `400 tokenizer_needed`.

## Decisions worth not re-litigating

**A model trained here is a library model like any other.** Once pretrained it is `local/<slug>`
in the library and its project's base, so chatting, correcting, fine-tuning, exporting and
serving it need nothing new.

**The estimate is computed, not stored.** A draft keeps only its design; counts and memory are
worked out on every read, so they follow the machine's GPUs and any fix to the formulas.
