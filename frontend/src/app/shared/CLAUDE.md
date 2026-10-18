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

`StatusPage` takes `titleKey` and `bodyKey` as translation keys, bound straight
from route `data` by `withComponentInputBinding()`. A new status page is a route
entry and two translation keys, not another component.

## Classes and methods

**`StatusPage`** — a full-page message on a `mat-card`, with one way back to the start; the
title and body are translation keys from the route's `data`.

**`Money`** (`<app-money [amount]>`) — an amount in Omani rials: three decimals, Latin
digits in both languages, the rial sign beside it and the currency's name for screen
readers. `RIAL_SIGN` is U+20C4.

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
