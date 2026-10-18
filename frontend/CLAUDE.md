# Frontend memory

Narrows the root `CLAUDE.md` to the Angular side. Read `.claude/docs/design-pattern.md` §3 for the layering contract; this file is the map.

## Layout

```
frontend/
  angular.json  tsconfig*.json  eslint.config.js  playwright.config.ts
  proxy.conf.json           /api, /admin, /static, /media → backend:8000
  e2e/                      Playwright journeys
  src/
    styles/_theme.scss      the Material 3 theme — every --mat-sys-* token, every override
    styles/_theme-colors.scss  M3 palettes generated from the brand gold
    styles/_tokens.scss     --app-* — spacing and what Material has no token for
    styles/_base.scss       element defaults, the focus ring for what is not Material
    styles/_layout.scss     page width + shell breakpoints — the only literal lengths
    styles/_reset.scss
    styles.scss
    app/
      app.{ts,html,scss}    the shell
      app.config.ts         providers
      app.routes.ts         top-level routes, one lazy entry per feature
      core/                 auth, i18n, http — what every feature depends on
      shared/               components used by more than one feature
      features/<feature>/   one directory per page (rule 13)
```

A feature directory:

```
features/<feature>/
  <feature>.routes.ts
  guards/<feature>.guard.ts
  pages/<page>/<page>.{ts,html,scss}
  state/<feature>.store.ts
  data/<feature>.api.ts
  data/<feature>.types.ts
  i18n/{en,ar}.json
  CLAUDE.md                 required (rule 3)
```

## The flow

```
Component  →  Store (signals)  →  Api  →  HttpClient
```

Each layer calls only the one below it. A component holding `HttpClient`, or a
store holding presentation state, is the pattern broken.

Feature stores are provided by the route, not `providedIn: 'root'` — the state
should die with the page. `AuthStore` and `LocaleStore` are root-provided because
the guards and the shell need the same instance.

## What the hook enforces

`.claude/hooks/guard-checks.py` runs after every edit and blocks:

- raw px in any `.scss` other than `_tokens.scss`, `_layout.scss` and `_reset.scss` (rule 12)
- `setTimeout` (rule 10)
- `confirm()`, `alert()`, `prompt()`, and a native `<dialog>`, `<select>`, radio or
  checkbox in a template — Material draws all four (rule 9)

`eslint.config.js` catches the same things earlier, plus `BehaviorSubject`
imports (rule 8) and unused symbols (rule 5).

## Conventions

**Path aliases.** `@core/*`, `@shared/*`, `@features/*`, `@styles/*`. A relative
path climbing past two levels is a sign the import should be an alias.

**Styles.** Colour, type, shape and elevation are Material's system tokens —
`var(--mat-sys-primary)`, `var(--mat-sys-body-large)`, `var(--mat-sys-corner-small)`,
`var(--mat-sys-level1)` — set once by `mat.theme()` in `src/styles/_theme.scss`. Spacing is
`var(--app-space-*)` from `src/styles/_tokens.scss`, which holds only what Material has no
token for. Logical properties only — `margin-inline-start`, never `margin-left` — so RTL is
free. No utility-class framework goes in alongside this, Tailwind included (see
`.claude/docs/design-pattern.md` §5).

`@use "layout" as *;` where a stylesheet needs the page width or a breakpoint
(`stylePreprocessorOptions.includePaths` puts `src/styles` on the path).

**Controls are Angular Material** (rule 9). Import each component a template uses —
`MatButton`, `MatFormField`, `MatInput`, `MatCard` — into the standalone component; never a
whole module for one directive. A feature stylesheet places Material components: their size, gap and
padding in the page. It never restyles one. A change to how every button looks is a
`mat.button-overrides(...)` in `_theme.scss`.

A field's error shows through `<mat-error>`, which `matInput` links with `aria-describedby`
and announces; a field validated from signals passes an `ErrorStateMatcher` that reads them
(`SignInPage` is the example). Busy is `[attr.aria-busy]` and `[disabled]` on the button.
Asking is `MatDialog`; a short report is `MatSnackBar`. Form fields keep Material's default
appearance, so no provider pulls `MatFormField` into the initial bundle.

**Do not write a focus ring.** `mat.strong-focus-indicators()` draws one on every Material
control, and `_base.scss` draws the same ring, in `--mat-sys-primary`, on everything else. A
component `outline` replaces it rather than adding to it.

Both colour schemes are live: the theme's `theme-type` is `color-scheme`, so every
`--mat-sys-*` colour is `light-dark(light, dark)` and the document follows the operating
system. **Look at a change in both.**

**Type.** Tajawal, self-hosted from `@fontsource/tajawal` through the build's `styles` in
`angular.json` — 400, 500 and 700, the theme's regular, medium and bold. `mat.theme()` sets
the family in every `--mat-sys-*` type token; nothing else names a font. Body text is
`--mat-sys-body-large`, `<h1>` is `--mat-sys-headline-medium`, `<h2>` is
`--mat-sys-title-large`, `<h3>` is `--mat-sys-title-medium` and `<h4>` is
`--mat-sys-title-small`, all from `_base.scss`; a feature never sets a heading's `font`. Code uses
`--app-font-mono`.

**Icons.** Font Awesome 7 Free, bundled: `angular.json` lists the package's
`fontawesome.css`, `solid.css` and `regular.css`, and the build copies the webfonts beside
them, so nothing is fetched at runtime and the icons work offline (ADR-009). They are drawn
through Material's `<mat-icon>`. `MAT_ICON_DEFAULT_OPTIONS` in `app.config.ts` makes
`fa-solid` the default font set, so a template names only the glyph:

```html
<mat-icon fontIcon="fa-user" />
<mat-icon fontSet="fa-regular" fontIcon="fa-user" />
```

That puts the glyph in the box Material's buttons, form-field prefixes and suffixes, menus
and lists already lay out; `_theme.scss` centres it there. The glyph renders on the element
itself through the webfont, so nothing rewrites it into an `<svg>`. Only the Free set ships:
`fa-thin`, `fa-duotone`, `fa-sharp` and Pro-only glyphs render nothing. Check a glyph in
`node_modules/@fortawesome/fontawesome-free/css/fontawesome.css` before using it.

`mat-icon` is `aria-hidden="true"` by default, so an icon is never self-describing: the
text beside it, or a translated `aria-label` on the `matIconButton` that carries the
behaviour, names the action. A `mat-icon` is never the button.

Font Awesome glyphs do not mirror themselves. Prefer a glyph with no direction, and where
direction is the point, add `class="mat-icon-rtl-mirror"`, which Material flips under
`[dir="rtl"]`.

**Strings.** Never a literal in a template. Feature bundles register on the
route with `provideTranslations(en, ar)`, so a feature's strings load with the
feature. A missing key renders as the key itself, on purpose.

**Errors.** The interceptor normalises every failure to `ApiError`. Stores read
`error.message` — already user-facing copy from the backend — and never inspect
status codes.

**Zoneless.** `provideZonelessChangeDetection()` is on. Anything mutating state
outside a signal will not render. That is the point.

## Classes and methods at the root

**`App`** (`app/app.ts`) — the skip link, the direction on the content and the router outlet.
Signed-in pages render inside `core/shell/`; sign-in renders alone. **`appConfig`** — zoneless change detection, the router with component input
binding and `paramsInheritanceStrategy: 'always'` (a page under `projects/:projectId` receives
`projectId` as an input), HTTP with the CSRF and error interceptors, Font Awesome as `mat-icon`'s
default font set, and the paginator's labels in the reader's language. **`routes`** — sign-in on its own, then the shell with every signed-in page as a child:
the start redirect (to Projects), one lazy entry per feature and the status pages. A project's
pages are the one place the app composes features: `projects/:projectId` loads the project
frame through `projectFrame()` and passes it the tabs the other features own (`chat`, `training`,
`versions`), so features never import each other. Per-module descriptions live in `core/`,
`shared/` and each feature's `CLAUDE.md`.

A route's `providers` are created once and kept, not once per visit — a store provided there
outlives its page, so a page that shows server data asks for it again when it opens.

## Commands

```bash
docker compose exec frontend npx ng build
docker compose exec frontend npx ng test --watch=false   # vitest, jsdom
docker compose exec frontend npx ng lint
docker compose exec frontend npx playwright test         # stack must be up
```

Unit tests are Vitest, not Karma — Karma is retired upstream and rule 4 says
nothing deprecated. Two consequences worth knowing: import `describe`/`it`/
`expect` from `vitest` explicitly, and reset the harness yourself in `afterEach`
with `TestBed.resetTestingModule()`, which Karma used to do for you.

Then look at the page in both languages. `dir="rtl"` is not a checkbox.

## Adding a slice

1. `features/<feature>/` with the layout above — the name matches the Django app.
2. Types first, in `data/<feature>.types.ts`, mirroring the backend contract, pagination
   envelope included. No other file declares an interface or type alias (rule 30).
3. Api → store → component → route → guard.
4. Both `i18n/en.json` and `i18n/ar.json`, registered with `provideTranslations`.
5. One lazy entry in `app.routes.ts`, with a guard (rule 11).
6. Write `features/<feature>/CLAUDE.md`. The `Stop` hook blocks finishing without it.
