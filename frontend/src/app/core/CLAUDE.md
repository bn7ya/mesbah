# core

What every feature depends on. **Not a feature** — no route of its own beyond
sign-in, no Django app mirroring its name.

Something belongs here only if a feature could not function without it. If two
features happen to use it, that is `shared/`. If one feature uses it, it belongs
in that feature.

## What lives here

```
core/
  auth/
    data/auth.types.ts      Identity — mirrors IdentitySerializer
    data/auth.api.ts        /api/auth/{csrf,login,logout,me,setup}
    state/auth.store.ts     root-provided; who the user is
    guards/auth.guard.ts    authGuard, guestGuard, groupGuard(...)
    roles.ts                the role ladder; roleGuard(role)
    pages/sign-in/          the sign-in page
    pages/setup/            the first-run page that creates the owner
  i18n/
    locale.store.ts         current language, the dictionary, the direction
    locale.types.ts
    translate.pipe.ts       {{ 'key' | t }}
    provide-translations.ts feature bundles register on their route
    paginator-intl.ts       mat-paginator's labels in the reader's language
    locale-switcher/        a mat-button-toggle-group: one exclusive choice of language
    {en,ar}.json            application-wide strings only
  http/
    api.types.ts            Page<T>, PageQuery, ApiError
    csrf.interceptor.ts     X-CSRFToken on unsafe requests
    error.interceptor.ts    every failure normalised to ApiError, its message in the reader's language
  shell/                    the frame every signed-in page renders in
    navigation.ts           the side menu's destinations
  ui/
    ui-mode.store.ts        Simple or Expert, persisted
    ui-mode-switcher/       the two-mode toggle
```

Its backend counterpart is `backend/apps/accounts/` — mounted at `/api/auth/`.

## Classes and methods

**`AuthApi`** (`auth/data/`) — the calls under `/api/auth/`: prime the CSRF cookie,
sign in, sign out, ask who the user is, and read the setup status and create the owner.

**`AuthStore`** (`auth/state/`) — who the user is, application-wide, as signals: the
identity, whether it has been resolved yet, busy, the last error, the groups and a display
name.
- `restore()` asks the backend on boot; a refusal means signed out, not an error.
- `signIn()` primes CSRF, signs in and reports success; `signOut()` always ends signed out
  on the sign-in page; `forget()` drops an identity the server no longer accepts.
- `setupNeeded()` asks whether a fresh install still needs its owner; `setUp()` creates the
  owner and signs them in.
- `hasGroup()`, `hasAnyGroup()`, `hasPermission()` decide what to show — superusers pass
  every check, as on the backend.

**Guards** (`auth/guards/`) — `authGuard` sends a signed-out visitor to sign in with a
return path; `guestGuard` keeps a signed-in user off sign-in and sends a fresh install to
setup; `setupGuard` lets only a fresh install onto setup; `groupGuard(...)` also
requires one of the named groups, or goes to `/forbidden`.

**Roles** (`auth/roles.ts`, Mesbah) — the ladder viewers → reviewers → trainers → admins
(`ROLE_LADDER`), mirroring `apps/members/roles.py`. `rolesFrom()` lists a role and every role
above it, `roleGuard()` is `groupGuard()` over `rolesFrom()`. The menu shows each destination
to its role and above.

**`SetupPage`** (`auth/pages/setup/`, Mesbah) — the first-run form: the setup code from the
terminal, a name, a username and a password; creates the owner through
`AuthStore.setUp()` and goes to the start page. A refusal shows in the shared `<app-note kind="error">`,
the one error box every page uses.

**`SignInPage`** (`auth/pages/sign-in/`) — the sign-in form on a `mat-card`: validates both
fields and shows each error through `mat-error` (an `ErrorStateMatcher` per field reads the
signals), toggles password visibility, signs in through the store and follows `?next=`. A refusal
shows in the shared `<app-note kind="error">`.

**`LocaleStore`** (`i18n/`) — the current language, persisted (Arabic until someone chooses), and the dictionary of every
registered bundle. Writes `lang` and `dir` on the document, and turns the CDK's root
`Directionality` with them, so Material components and overlays follow the language.
`translate()` resolves a key and fills `{name}` placeholders, isolating a value written in the
other script (a Latin name in Arabic, an Arabic one in English) so it keeps its own direction; a
missing key renders as itself. `register()` adds a feature's bundles.

**`LocalePaginatorIntl`** (`i18n/paginator-intl.ts`) — every `mat-paginator`'s labels and range
in the reader's language, refreshed when the language changes. Provided in `app.config.ts`.

**`TranslatePipe`** (`t`) — `translate()` in a template; impure so a language switch reaches
text already on screen. **`provideTranslations()`** registers a feature's bundles when its
route activates. **`LocaleSwitcher`** — the two-language toggle, a Material button-toggle
group with each option in its own language.

**`Shell`** (`shell/`) — the frame of every signed-in page: a side menu (`NAVIGATION`) that
stays open on wide screens and slides over on narrow ones, a top bar with the Simple/Expert
switch, the language switch and the user's menu, and the `<main id="main">` the skip link
targets (`tabindex="-1"`, so the skip link can focus it). On narrow screens the switches and
sign-out move into the side menu.

**`UiModeStore`** (`ui/`) — Simple or Expert, persisted like the language; Simple until someone
chooses. `expert` is the `computed` pages read to show more technical detail.
**`UiModeSwitcher`** — the two-mode toggle, a Material button-toggle group.

**`csrfInterceptor`** (`http/`) — sends Django's CSRF token on unsafe requests. Auth is a
same-origin session cookie, so CSRF is the price, and the built-in Angular option skips
absolute URLs and uses other names. **`errorInterceptor`** — turns every failure into an
`ApiError`. When the server says the session has gone (401, or 403 `not_authenticated` or
`authentication_failed`, outside `/api/auth/`), it forgets the identity, so `guestGuard` lets the
user through, and sends them to sign in with `next`; a `permission_denied` 403 stays an error on
the page. When a bundle has
`errors.<code>` for the error's code, that text replaces the server's English message, so a
feature adds its error codes to its own bundle and every store keeps reading `message`. A code
with no text keeps the server's message in English and becomes `errors.generic` in any other
language, so Arabic never shows English prose. The sign-in refusals (`authentication_failed`,
`account_deactivated`) are in the core bundles. An error
body that arrives as text, from a request made with `responseType: 'text'` such as a stream, is
parsed as JSON first.

## Decisions worth not re-litigating

**Auth lives in `core/`, not `features/auth/`.** This is the documented
exception to rule 13's name mirroring. Guards and the HTTP interceptor need
`AuthStore`, and neither may import from a feature. A *page* built on auth — a
profile screen, user administration — is a normal slice with a mirrored name.

**Session cookies, not tokens.** Same-origin in both environments, so an
`HttpOnly` session cookie works and cannot be read by injected script. The price
is CSRF, which `csrfInterceptor` and `/api/auth/csrf/` pay.

**The three guards share `ensureSignedIn()`, a plain function.** `CanActivateFn`'s
return type includes `Observable`, which does not narrow — so a guard that calls
another guard cannot check the answer. Composing the helper instead of the guard
keeps `groupGuard` type-safe.

**`AuthStore.resolved` exists so guards do not act too early.** On a cold load
nobody has called `/me/` yet; without the flag, `authGuard` would bounce a
signed-in user to sign-in on every refresh.

**Group and permission checks here are convenience (rule 21).** They decide what
is *shown*. What a user may *do* is decided by `permission_classes` on the
endpoint, on every request. A guard without a matching backend check is
decoration, and shipping one is a security finding.

**A missing translation renders as its key.** Silently blank text hides the bug
until a user finds it.

**`LocaleStore` sets the CDK's `Directionality`, not a `[dir]` directive on the shell.**
The CDK reads the document's `dir` once, when it is first injected, and never again. A
`[dir]` binding would only reach what renders inside it; a dialog, menu or snack bar opens
in an overlay outside the shell and takes the root service's direction. Setting the root
`valueSignal` and emitting `change` turns both.

**The error interceptor redirects only when the session has gone, and never under `/api/auth/`.**
A 401 from the sign-in endpoint means wrong credentials, not a lost session; redirecting there
would loop. A 403 that is about permission keeps the user where they are.

## Changing anything here

Every feature is downstream. `Identity`, `Page<T>` and `ApiError` are the
frontend half of the backend contract — change them and
`backend/apps/common/` or `backend/apps/accounts/` changes in the same slice.
