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

`StatusPage` takes `titleKey` and `bodyKey` as translation keys, bound straight
from route `data` by `withComponentInputBinding()`. A new status page is a route
entry and two translation keys, not another component.

## Classes and methods

**`StatusPage`** — a full-page message on a `mat-card`, with one way back to the start; the
title and body are translation keys from the route's `data`.

**`Money`** (`<app-money [amount]>`) — an amount in Omani rials: three decimals, Latin
digits in both languages, the rial sign beside it and the currency's name for screen
readers. `RIAL_SIGN` is U+20C4.

**`Term`** (`<app-term key="vram" />`) — a technical term followed by a small help button; the
button opens a note with the term's explanation (`glossary.<key>.term` and `.explain` in the
core bundles), closed by Escape or a click outside. Built on the CDK overlay, since Material
has no popover.

**`Meter`** (`<app-meter [label] [totalBytes] [segments]>`) — a bar split into coloured
segments plus the free remainder, with a legend that carries the same numbers in text and an
`aria-label` that reads them all.

**`formatBytes()`**, **`formatNumber()`**, **`formatCompact()`**, **`BytesPipe`**,
**`CompactPipe`** (`format/`) — sizes in binary units labelled B…PB, wrapped in Unicode isolates
so "16 GB" keeps its order in an Arabic sentence; numbers with Latin digits in both languages;
and counts shortened the way the language writes them ("8.2B", "9.1M" in English, "8.2 مليار"
in Arabic).

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
