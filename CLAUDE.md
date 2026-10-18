# Project Memory

This is the root memory file. Every session reads it. `frontend/CLAUDE.md` and `backend/CLAUDE.md` narrow these rules to their side; each feature directory carries its own `CLAUDE.md`.

## Mesbah

**مصباح · Mesbah** ("lamp") is a studio for customizing language models, for one person or
a whole team. Pick any model on HuggingFace, chat with it, correct its replies and its
thinking in place, add HuggingFace datasets, and train. Every training run adds a
**version** that stores only the change to the model's weights, so versions are cheap to
keep, branch and roll back. A version runs on the built-in engine or on vLLM, llama.cpp or
Ollama, exports to their formats, and is served over OpenAI- and Ollama-compatible APIs.
Mesbah can also design and pretrain a new model from scratch, MoE or encoder-decoder.

| Concept | What it is |
|---|---|
| Project | one model being customized: a HuggingFace base, or a model designed from scratch |
| Version | a node in a project's tree; the root is the base, every other node is one LoRA delta measured from the base |
| Conversation / message | a chat with a version; an edited reply or thinking chain is a correction |
| Dataset | an install-wide library entry: a HuggingFace import, an upload, or a project's published corrections |
| Training run | turns corrections and datasets into a new version |
| Engine / deployment | an OpenAI-compatible server a version runs on |

It is this Template's product, so every rule below holds. Where Mesbah departs from the
Template, an ADR in `.claude/docs/adr/` (003 onward) says why. Mesbah edits these
Template-owned files, so `/template-sync` conflicts in them are expected:
`compose.yaml`, `backend/config/settings/base.py`, `frontend/src/index.html`,
`frontend/src/app/core/i18n/{en,ar}.json`, `frontend/src/app/core/i18n/locale.store{,.spec}.ts`,
`frontend/src/app/core/CLAUDE.md`, `frontend/CLAUDE.md`, `frontend/angular.json`,
`frontend/package.json`, `.claude/docs/interface.md`, `.gitignore`,
`frontend/src/app/app.{html,scss,routes.ts,config.ts}`, `frontend/src/app/core/http/error.interceptor.ts`,
`frontend/src/app/core/auth/pages/sign-in/sign-in.html`, `frontend/src/app/shared/status-page/`,
`frontend/src/app/shared/CLAUDE.md`, `frontend/src/styles/{_theme,_tokens,_layout,_base}.scss`,
`backend/pyproject.toml`, `backend/config/urls.py`, `backend/CLAUDE.md`,
`.claude/docs/language.md`, `README.md` and this file.

Mesbah handles no money. `MoneyField`, `<app-money>` and the rial font stay because they
are the Template's, kept so sync applies cleanly; rule 5 does not remove them.

The interface is Arabic first: a new visitor gets Arabic, and English is one switch away.
Model names and a fixed technical vocabulary (LoRA, GPU, VRAM, loss…) render as-is,
always beside an explanation (ADR-007, `.claude/docs/language.md`).

## Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 22 (standalone, signals, zoneless, TypeScript 6) + Angular Material 22 (Material 3) + Font Awesome 7 Free (bundled) |
| Backend | Django 5.2 LTS + Django REST Framework + drf-spectacular (OpenAPI 3 / Swagger) |
| Database | PostgreSQL 18 + pgvector 0.8.6 |
| Cache / broker | Redis 8 |
| Background jobs | Celery 5.6 + django-celery-beat |
| Backups | django-dbs — encrypted, redundant, self-healing |
| Serving | gunicorn (WSGI) behind nginx; Angular built statically |

## The design pattern

**Vertical Slice + Service/Repository.** Read `.claude/docs/design-pattern.md` before writing any code. It is the single source of truth for structure, layering and the definition of done. Deviating requires a new ADR in `.claude/docs/adr/`.

The short version: one Angular feature directory mirrors one Django app mirrors one page. Backend flows `View → Service → Repository → Model`. Frontend flows `Component → Store → Api → HttpClient`. Each layer may only call the one below it.

## Hard rules

These are not preferences. The `PostToolUse` hook blocks edits that violate the mechanical ones.

1. **One design pattern.** Vertical Slice + Service/Repository, everywhere, always.
2. **Slice vertically.** No change ships frontend-only or backend-only. If you were asked for one side, build the other side too or say explicitly why it is not needed.
3. **A `CLAUDE.md` per feature**, on both sides. A feature directory without one is unfinished work.
4. **Nothing deprecated.** No deprecated Angular, Django or DRF APIs. If you find one, replace it.
5. **Nothing unused.** A function, import, style, translation key or endpoint with no caller gets deleted — not commented out, not left "just in case".

### Angular

6. Standalone components only.
7. `.ts`, `.html` and `.scss` are always three separate files. Never inline `template:` or `styles:`.
8. State is signals (`signal`, `computed`, `linkedSignal`, `resource`). Do not use `BehaviorSubject` for view state.
9. **Angular Material for every control.** A button is `matButton` or `matIconButton` on a
   native `<button>` or `<a>`; a field is `mat-form-field` with `matInput`; a card, a
   choice, a dialog, a menu, a select, a table is its Material component. A control Material
   lacks becomes a component in `shared/` built on the CDK, never a second copy in a
   feature. Never `confirm()`, `alert()` or `prompt()` — `MatDialog` asks, `MatSnackBar` or
   a message in the page reports, a form field collects. The guard blocks a native
   `<dialog>`, `<select>`, radio or checkbox.
10. No `setTimeout`. Model timing in state.
11. Every route has a guard. Every one.
12. **No raw px in feature styles.** Colour, type, shape and elevation are Material's system
    tokens, read as `var(--mat-sys-*)` and set once by the theme in `src/styles/_theme.scss`.
    Spacing and the few values Material has no token for are `var(--app-*)` from
    `src/styles/_tokens.scss`. `src/styles/_layout.scss` holds the page's maximum width and
    the shell's breakpoints (a media query cannot read a custom property). Those two files
    and `_reset.scss` are the only ones exempt. A feature places Material components; how one
    looks changes in `_theme.scss`, through `mat.<component>-overrides()`, for the whole app.

    `.claude/docs/interface.md` is how a screen is composed out of those tokens: hierarchy,
    states, type, space, colour, depth, icons. `/ui-review` reviews a screen against it.

### Django

13. One app per frontend page, same name on both sides.
14. **No `.objects.` outside a `repositories/` module.** No raw SQL in application code.
15. Every model inherits `apps.common.models.BaseModel` (uuid pk, `created_at`, `updated_at`, `deleted_at`, `created_by`).
16. **Soft delete only.** `delete()` sets `deleted_at`. Hard deletion is a data migration, never an application action.
17. Every list endpoint paginates.
18. Auth is required by default. A public endpoint declares `permission_classes = [AllowAny]` explicitly.
19. Split `models.py` / `views.py` / `serializers.py` into packages past ~3 items, re-exporting from `__init__.py`.

### Auth

20. Django auth plus Django Groups and Permissions are the only authorization system. No parallel roles table.
21. The frontend reads group names from `/api/auth/me/` and uses them in route guards and to show or hide affordances. Frontend checks are convenience; the backend check is the security boundary. Never one without the other.

### Language

22. **The UI is bilingual.** Every user-facing string exists in both `en.json` and `ar.json`
    with identical key sets, and the UI works in RTL.

    a. Every user-facing string goes through a bundle — never hardcoded in a template.
    b. CSS logical properties only (`margin-inline-start`, `inset-inline-end`,
       `text-align: start`). Never `left`/`right`.
    c. Content renders in its own direction inside a UI of either language — `dir` on the
       content element only, never on the row.
    d. The backend sends keys, not prose. An error carries a stable `code` the frontend
       resolves; prose that lives in the database carries an `_ar` column beside it.
    e. **Both languages are written plainly, as a native product would write them.**
       `.claude/docs/language.md` is the standard: no tashkeel, no verb that gives the
       product intent, no aside for a sceptic, no count before a noun, a title that names
       the page, one word per concept. The Arabic is written from the meaning, never from
       the English word order, and is read without the English beside it. The guard hook
       enforces the tashkeel rule; the rest is the copywriter's and translator's judgement.

### Types

30. **Everything is typed, and the checker agrees.**

    a. TypeScript never uses `any` — name the type, or take `unknown` and narrow it.
    b. Every `interface` and `type` alias lives in a sibling `<name>.types.ts` and is
       imported with `import type`. A component, store or api file declares none.
    c. Python annotates every function signature and every variable where it is first
       bound — `name: Type = value`, module constants and settings included. A class body's
       Django fields and `Meta` are declarations already, and a name rebound later keeps the
       type it was given.
    d. `mypy --strict`, with the Django and DRF plugins, is part of the gate. `Any` in a
       signature needs a reason a reviewer would accept; `object` usually does the job.

    ESLint, ruff `ANN`, mypy and the guard hook each enforce a part of it.

### Comments

31. **Code carries almost no comments; one file describes the module.**

    a. No docstrings, no JSDoc, no `/* … */` blocks in application code (`backend/`,
       `frontend/src/`, `frontend/e2e/`). Names and types say what the code does.
    b. A comment is the exception: one or two lines saying *why*, where the reason cannot be
       read from the code — a framework constraint, a deliberate empty block. Lint pragmas
       (`noqa`, `eslint-disable`, `type: ignore`) are not comments.
    c. Each module's `CLAUDE.md` has a `## Classes and methods` section describing every
       class and public method in a line or two, abstractly. That is the one file a reader
       opens, and it changes in the same commit as the code it describes.

    The guard hook blocks a docstring, a JSDoc block, and any comment longer than two lines.

### Money

29. **Amounts are Omani rials, drawn with the Central Bank of Oman's sign (U+20C4).** The
    backend stores and sends them as `apps.common.fields.MoneyField` — three decimal places,
    a string in JSON, no currency code beside it. The frontend renders every amount with
    `<app-money [amount]="…" />`, which sets the sign beside the amount in Latin digits, in
    both languages. Never `OMR`, `O.R.`, `R.O.`, `ر.ع.` or `﷼` — the guard blocks them in
    templates, bundles and the API. No system font draws the sign yet, so
    `src/styles/_fonts.scss` serves it from a one-glyph webfont (`public/fonts/`, subset
    from JuliaMono under the OFL) scoped to U+20C4 by `unicode-range`.

### Assets

32. **Never draw an SVG by hand** — no logo, illustration, picture or icon written as path
    data — unless the developer asks for exactly that. A logo or picture is supplied by the
    developer or comes from a licensed source and lands in `frontend/public/`; an icon is
    Font Awesome; a glyph missing from a font comes from a published font, subset (the rial
    sign is how). When none of those has it, ask — a guessed drawing ships as if it were
    the real mark.

## How work gets orchestrated

Start in plan mode — it is the default (`permissions.defaultMode: "plan"`).

`architect` plans first, always. It fixes the slice boundary and dispatches specialists in order. Typical order for a new feature:

```
architect
  → django_engineer      (model → repository → service → view → serializer)
  → angular_engineer     (api → store → component → route → guard)
  → interface_designer   (tokens, spacing, hierarchy, states)
  → copywriter           (all user-facing copy)
  → translator           (the Arabic, written from the meaning; copywriter re-reads it)
  → user_journey_engineer(black-box test the running app)
  → naive_user           (a first-time visitor tries the tasks; reports how hard they were)
  → cleaner              (dead code, pattern conformance)
```

`naive_user` gets the URL and the tasks in a user's words, and nothing else — no code, no
file names, no hint at which button to press. Its only tools are the `playwright` MCP server's
browser actions (`.mcp.json`), so it cannot read the source even by accident. Where the
browser Playwright downloads is not the one installed, set `PLAYWRIGHT_MCP_EXECUTABLE_PATH`
(and `PLAYWRIGHT_MCP_SANDBOX=false` inside a container) in the environment.

`logic_engineer` is pulled in for algorithmically heavy work. `db_engineer` reviews anything touching queries, indexes or vectors. `unifier` sweeps periodically, not per-feature. `mcp_engineer` handles tooling integrations.

## The agents

| Agent | Model | Use it for |
|---|---|---|
| `architect` | opus | Planning any feature as a vertical slice, then dispatching |
| `interface_designer` | sonnet | Spacing, type scale, hierarchy, states, the Material theme and the `--app-*` tokens |
| `copywriter` | sonnet | Every user-facing string |
| `unifier` | sonnet | Auditing design and language consistency across the app |
| `logic_engineer` | opus | Heavy algorithmic work, front and back |
| `user_journey_engineer` | opus | Black-box testing the running app via Playwright |
| `naive_user` | haiku | A first-time visitor: given only a URL and plain tasks, rates how hard each one was |
| `mcp_engineer` | sonnet | Finding, building and connecting MCP servers |
| `translator` | sonnet | The Arabic interface — written from the meaning — plus parity and RTL |
| `cleaner` | sonnet | Behavior-preserving cleanup and pattern enforcement |
| `db_engineer` | sonnet | Query plans, indexes, benchmarks, pgvector |
| `angular_engineer` | sonnet | Frontend implementation |
| `django_engineer` | sonnet | Backend implementation |

## The design system

**Angular Material (Material 3) is the design system**, themed once. `ADR-002` in
`.claude/docs/adr/` records why.

| File | Holds |
|---|---|
| `src/styles/_theme.scss` | `mat.theme()` — colour from the brand palettes, Tajawal, density — and the strong focus indicators. Every `--mat-sys-*` token, and every component override |
| `src/styles/_theme-colors.scss` | The M3 palettes, generated from the brand gold by `ng generate @angular/material:theme-color` |
| `src/styles/_tokens.scss` | What Material has no system token for, as `--app-*`: the space scale, the focus width, the icon box, motion, layers |
| `src/styles/_base.scss` | Element defaults — body type and colour, headings, links, the focus ring for what is not Material, the skip link |
| `src/styles/_layout.scss` | The page's maximum widths and the shell's breakpoints |

The theme's colour scheme follows the operating system: every `--mat-sys-*` colour is
`light-dark()`, so light and dark are both live.

**Tajawal is the typeface**, in both languages — one family with matched Arabic and Latin
designs, so a mixed sentence sets on one font. It is self-hosted from `@fontsource/tajawal`
(weights 400, 500 and 700, the theme's regular, medium and bold), so the build fetches
nothing at runtime, and Material's type scale (`--mat-sys-body-large`,
`--mat-sys-headline-medium` and the rest) is set in it. A fourth weight is a new
`@fontsource/tajawal/<weight>.css` entry in `angular.json` and a theme change, never a
`font-weight` number in a feature.

Icons are Font Awesome 7 Free, bundled by `angular.json` from `@fortawesome/fontawesome-free`
(solid and regular; ADR-009), drawn through `<mat-icon>`:
`MAT_ICON_DEFAULT_OPTIONS` makes `fa-solid` the default font set, so
`<mat-icon fontIcon="fa-eye" />` sits where Material's buttons, fields and menus expect an
icon. `mat-icon` is `aria-hidden` by default; the text or `aria-label` beside it names the
action. No Material Symbols font ships. Keyboard patterns — a listbox, a menu, tabs — come
from the Material component, or from the CDK where Material has none.

## Running the stack

```bash
cp .env.example .env
docker compose up --watch --build          # dev — hot reload both sides
```

| What | Where |
|---|---|
| Angular | http://localhost:4200 |
| API (proxied) | http://localhost:4200/api/ |
| Swagger UI | http://localhost:4200/api/schema/swagger-ui/ |
| Django admin | http://localhost:4200/admin/ |

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build   # prod
```

The Angular dev server proxies `/api`, `/admin` and `/static` to Django via `frontend/proxy.conf.json`, so dev is same-origin and needs no CORS configuration — matching how prod behaves behind nginx.

## Branches

`main` is the trunk. Work happens on a branch off it, named for the issue it
closes and what it does — short, lowercase, hyphenated, no session ids or
generated suffixes.

```
kind/issue-what-it-does
```

`kind` is one of `feat`, `fix`, `docs`, `chore`, `refactor`, and matches the type
of the commits on the branch. Then the issue number, then two or three words a
person would recognise in a branch list:

```
feat/12-orders-page
fix/18-rtl-table-alignment
docs/24-backup-runbook
chore/31-bump-angular
```

When a request became several issues, the branch takes the lowest number of the
batch — the branch delivers the slice, the issues are its steps.

One slice per branch. If the name needs an "and", it is two branches.

## How work gets committed

Read `.claude/skills/git-flow/SKILL.md` before starting any feature, fix or
refactor. These are the rules it enforces; they carry the same weight as the
hard rules above.

23. **An issue before the first edit.** Every feature, fix and refactor opens a
    GitHub issue first, and the work references it. Documentation and chores do
    not need one.
24. **One issue, one commit, one working application.** Split a request by
    behaviour, never into a backend commit and then a frontend commit — that
    first commit is one you cannot return to. Every commit stands on its own:
    check it out and the app runs.
25. **The gate before the commit.** Run what CI runs — ruff, mypy, migrations check,
    spectacular, pytest, ng lint, the production build, ng test, and
    `compileall` over the hooks. Red is not a commit. CI itself runs only when a
    branch merges into `main`, so this gate is the only check a branch gets before then.
26. **Conventional subjects.** `<type>(<scope>): <subject> (#N)`, then a body
    explaining why, then the `Verified against …` paragraph, then `Closes #N`.
27. **Push every green commit, one PR per branch.** A commit on one machine is
    not a backup. The PR closes every issue in the batch.
28. **A session declares itself and reads the others.** Several Claude sessions run on
    this machine at once, often in different worktrees, so before you edit a file, commit
    to a branch, or start the gate, know who else is doing it. The hooks say so without
    being asked; `/sessions` is how you look, and how you message a peer by name. Never
    take a resource another live session announced without deciding to.

## Session awareness

Every session writes a short document about itself — its worktree, branch, issue, and what it was last asked to do — and reads every other live session's. Four hooks do it: `SessionStart` prints who else is live, `UserPromptSubmit` speaks only when that set changes, and two `PreToolUse` hooks warn before you edit a file another live session is holding or start a command that takes the gate, the test database or the compose project.

It **warns and lets you through**. One person drives every session, so the decision belongs with them, not with a hook. Nothing here takes a lock, and nothing waits on anything.

The documents live in `$XDG_RUNTIME_DIR/claude-sessions/`, never in the repository — the contention is over one machine, not one repository, and tmpfs means a reboot clears it correctly. Liveness comes from `/proc`, never from a heartbeat.

`.claude/docs/sessions.md` is the full protocol and the reasoning. `CLAUDE_SESSIONS_OFF=1` turns it off; `/sessions` is the skill.

## Template sync

A product cut from this Template keeps taking its improvements. `.claude/template.json`
names the Template repository and the last commit taken from it; a `SessionStart` hook
fetches the Template at most every six hours and, when it has moved on, lists the commits
this repository has not taken. `/template-sync` replays them on a `chore/sync-template`
branch — a diff, not a merge, because a repository made with "Use this template" shares no
history with it. In the Template itself the hook stays silent. `CLAUDE_TEMPLATE_SYNC_OFF=1`
turns it off.

## Prompt log

Every prompt submitted in this project is appended to `prompt.txt` by a `UserPromptSubmit` hook. The file is gitignored and stays on the machine that wrote it — it is a local record of what was asked, not part of the repository. Do not edit it by hand.
