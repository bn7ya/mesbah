# ADR-002: Angular Material is the component layer

**Status:** accepted — 2026-10-06 (#44)
**Supersedes:** the app-owned control classes the Template carried after #36, and every
earlier component library.

## Context

The Template has changed component layers three times. The last was a handful of native
elements styled by app-owned classes — honest, but small: a button, a field, a card, a
toggle. Every product cut from the Template would have had to grow it by hand into a dialog,
a menu, a select, a table, a date picker, a snack bar, each with its own keyboard model,
focus trap, overlay and RTL behaviour.

## Decision

**Angular Material (Material 3) draws every control.** One theme, `src/styles/_theme.scss`,
calls `mat.theme()` with palettes generated from the brand gold
(`ng generate @angular/material:theme-color --primary-color=#7a5c12` →
`_theme-colors.scss`), Tajawal as the type family, and the default `color-scheme` theme type, so every
`--mat-sys-*` colour is `light-dark()` and the document follows the operating system.
`mat.strong-focus-indicators()` gives every Material control a visible focus ring in the
primary colour; `_base.scss` draws the same ring for everything else.

- **Colour, type, shape and elevation are Material's system tokens** — `--mat-sys-primary`,
  `--mat-sys-on-surface-variant`, `--mat-sys-headline-medium`, `--mat-sys-corner-small`,
  `--mat-sys-level1` and the rest. There is no second name for any of them.
- **`_tokens.scss` keeps only what Material has no system token for** — the `--app-space-*`
  scale, the focus width, the icon box, a duration and an easing, the skip link's layer.
- **A component's look changes in one place:** `mat.<component>-overrides(...)` in
  `_theme.scss`. A feature stylesheet places Material components; it never restyles one.
- **Font Awesome 7 Pro stays the icon set.** `MAT_ICON_DEFAULT_OPTIONS` makes `fa-solid` the
  default font set, so `<mat-icon fontIcon="fa-eye" />` draws a Font Awesome glyph in the box
  Material's buttons, fields, lists and menus already lay out. No Material Symbols font ships.
- **The CDK follows the language.** `LocaleStore` sets the root `Directionality` whenever it
  writes `dir` on the document, so overlays and bidi-aware components turn with the page.
- **No `@angular/animations`.** Material animates in CSS; `provideAnimationsAsync()` is
  deprecated and not provided.
- **Form fields use Material's default (filled) appearance.** An app-wide
  `MAT_FORM_FIELD_DEFAULT_OPTIONS` provider would pull `MatFormField` and `@angular/forms`
  into the initial bundle for every page; the default costs nothing.

## Consequences

- Rule 9 reads: Angular Material for every control. Never `confirm()`, `alert()` or
  `prompt()` — `MatDialog` asks, `MatSnackBar` or an in-page message reports, a form field
  collects. The guard blocks a native `<dialog>`, `<select>`, radio or checkbox input.
- Rule 12 reads: no raw px in feature styles; colour, type, shape and elevation are
  `var(--mat-sys-*)`, spacing is `var(--app-space-*)`.
- The initial bundle grows by the CDK and `MatIcon` (about 26 kB raw); components load with
  the lazy route that uses them.
- Material's density, shapes and motion are the defaults. Changing one is a theme override
  and a decision for the whole application, never a feature's.
