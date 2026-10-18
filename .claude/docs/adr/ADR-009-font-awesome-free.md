# ADR-009: Mesbah bundles Font Awesome Free

**Status:** accepted — 2026-10-18 (#4)
**Supersedes:** the "Font Awesome 7 Pro stays the icon set" point of ADR-002, for Mesbah.

## Context

The Template loads Font Awesome Pro as a kit script from `kit.fontawesome.com`. The kit
needs the internet, honours a domain allow-list and counts against the subscription's
quota. Mesbah installs with `pip install mesbah` and runs on a laptop, often offline, or on
an internal host nobody added to the kit. There the icons vanish. Pro files also cannot be
shipped inside a public package.

## Decision

- Icons come from `@fortawesome/fontawesome-free`, listed in `angular.json` styles
  (`fontawesome.css`, `solid.css`, `regular.css`). The build copies the webfonts, so every
  build, the wheel and the Docker image carry their icons.
- `index.html` loads no kit script.
- `<mat-icon fontIcon="fa-…" />` with `fa-solid` as the default font set is unchanged;
  `fa-regular` is the only other style.
- Only Free glyphs are used. A Pro-only glyph or style renders nothing, so a new glyph is
  checked against the package's `fontawesome.css` first.

## Consequences

The thin, duotone and sharp styles and the Pro-only glyphs are gone. A `/template-sync`
that touches `index.html` or the icon docs needs this decision reapplied.
