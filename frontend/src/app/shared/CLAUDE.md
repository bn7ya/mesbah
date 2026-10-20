# shared

Components, pipes and directives used by **more than one** feature.

The bar is two callers. Used by one feature — it belongs in that feature. Needed
by every feature to function at all — it belongs in `core/`. Moving something
here early is how a shared directory fills with things nobody shares.

`shared/` must never import from `@features/*`. That dependency runs the wrong
way and turns a shared component into a feature's private one.

## What lives here

| Component | Used by |
|---|---|
| `status-page/` | `/forbidden`, `/**` — any full-page dead end with one way out |
| `money/` | Every amount of money, in every feature (rule 29) |
| `term/` | Every technical term on screen, with its explanation (ADR-007) |
| `meter/` | Memory and disk shown as a bar with a legend |
| `format/` | Sizes and numbers in the reader's language, Latin digits |
| `confirm-dialog/` | Asking before an action that removes or replaces something |
| `version/` | A version's label and its name in words, and the announcement that keeps the project frame's chip current (projects and versions) |
| `note/` | Every message in a box: a failure (`kind="error"`, `role="alert"`) and a hint the reader may need (`role="note"`, or `role="status"` with `live`) |
| `empty-state/` | A list, table or panel with nothing in it: an icon, a title, the reason and, when there is one, the way out |
| `status/` | A state or a tag as an icon and a word — a run, an engine, a download, a member, "Default" |
| `fit-verdict/` | Whether a model fits this machine, as a `status` with the verdict's own icon |
| `code-block/` | A command, an address or an error's detail in a monospace block that scrolls sideways inside itself, with room beside its label for a Copy button |

`StatusPage` takes `titleKey` and `bodyKey` as translation keys, bound straight
from route `data` by `withComponentInputBinding()`. A new status page is a route
entry and two translation keys, not another component.

## Classes and methods

**`StatusPage`** — a full-page message on a `mat-card`, with one way back to the start; the
title and body are translation keys from the route's `data`.

**`Money`** (`<app-money [amount]>`) — an amount in Omani rials: three decimals, Latin
digits in both languages, the rial sign beside it and the currency's name for screen
readers. `RIAL_SIGN` is U+20C4.

**`Term`** (`<app-term key="vram" />`) — a technical term followed by a small help button, named
"Explain: {term}" (`glossary.explainTerm`) for screen readers; the
button opens a note with the term's explanation (`glossary.<key>.term` and `.explain` in the
core bundles), closed by Escape or a click outside. Built on the CDK overlay, since Material
has no popover.

**`Meter`** (`<app-meter [label] [totalBytes] [segments]>`) — a bar split into coloured
segments plus the free remainder, with a legend that carries the same numbers in text and an
`aria-label` that reads them all.

**`formatBytes()`**, **`formatNumber()`**, **`formatCompact()`**, **`formatSignificant()`**,
**`formatPercent()`**, **`isolateLtr()`**, **`formatDateTime()`**, **`BytesPipe`**, **`CompactPipe`**,
**`DateTimePipe`** (`format/`) — sizes in binary units labelled B…PB, wrapped in Unicode isolates
so "16 GB" keeps its order in an Arabic sentence; numbers with Latin digits in both languages;
counts shortened the way the language writes them ("8.2B", "9.1M" in English, "8.2 مليار"
in Arabic); a number to a set count of significant digits; a ratio as an isolated percentage;
and a timestamp as a date with the time, in the reader's language — a long date by default,
`'medium'` where the line is short (`{{ when | datetime: 'medium' }}`). `isolateLtr()` wraps
any Latin text, such as a repository name, in the same isolates so it keeps its order inside an
Arabic sentence.

**`ActiveVersionChanges`** (`version/`) — a root service the versions page announces the
active version on (`announce()`, a project id and a `VersionLabel`), and the project frame
listens to (`changes`); nothing is replayed to a late listener. **`VersionNamePipe`** and
**`versionName()`** — a version's name for display: the backend's seeded `base` on version 0
reads "Base model" in the reader's language, any other name stays. `VersionLabel` is the shape
a project carries its active version in.

**`Note`** (`<app-note [kind] [icon] [live]>`) — the one box for a message. `kind="error"` is the error
container with `fa-circle-exclamation` and `role="alert"`; the default is a hint on the secondary
container with `fa-circle-info` and `role="note"`, or `role="status"` when `live` (a hint that
changes as the form does). `icon` swaps the glyph. The text is the content; a Retry button goes
under the box, not in it.

**`EmptyState`** (`<app-empty-state [icon] [heading]>`) — an outlined card with the icon, the title
in `title-medium`, the content as the reason in the secondary tone, and any element marked
`emptyActions` as the buttons below it. Used where a section would otherwise show nothing, inside
a page and inside a dialog alike.

**`Status`** (`<app-status [icon] [tone] [prominent]>`) — an icon and a word on one line.
`tone="ok"` draws the icon in the accent, `"error"` colours both, the default is the secondary
tone. `prominent` sets it in `title-medium` for a card's headline state. State is never colour
alone, so the word always comes with the icon.

**`FitVerdict`** (`<app-fit-verdict [verdict] [prominent]>`) — a `Status` whose icon follows the
verdict (`FIT_ICONS`) and whose tone is `error` only when the model is too large. The word is the
content, translated by the feature that renders it.

**`CodeBlock`** (`<app-code-block [code] [label]>`) — a `pre` in `--app-font-mono`, left to right,
never wrapped: a long line scrolls inside the block, so the page never scrolls sideways. Once
the block really scrolls (measured after render and on viewport changes) it is a `region` in the
tab order, named by its `label` or `codeBlock.name`. The `label` and anything projected into
it (a Copy button) sit in a bar above.

**`ConfirmDialog`**, **`confirmAction()`** (`confirm-dialog/`) — a `MatDialog` that asks one
question with translation keys and resolves to `true` only on the confirming button; a
`destructive` question colours that button with the error tone.

## Conventions

Same rules as a feature component: standalone, `OnPush`, three files, Angular Material for
every control, colour and type as `var(--mat-sys-*)`, spacing as `var(--app-space-*)`, no
raw px.

A control Material does not have, needed by two features, is built here on the CDK and
themed from `--mat-sys-*` — never a second look beside Material's.

Strings that a shared component renders live in `core/i18n/{en,ar}.json`, since
there is no one feature bundle to put them in.

`unifier` audits this directory: when the same fix appears in three features, it
belongs here instead.
