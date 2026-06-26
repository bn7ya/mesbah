# frontend/ — Angular 20 + PrimeNG, RTL minimal UI

Standalone components, signals, no NgModules. PrimeNG 20 + `@primeuix/themes`
(Aura preset tuned to a neutral blue accent) for components; **Tailwind v4** for all
layout/spacing/colour. The whole app is **RTL Arabic**; technical terms stay English.

## Run / verify
```bash
npm install
npm start          # http://localhost:4200, proxies /api (+ WS) → :8077
npm run build      # must be warning-clean

# desktop shell (Tauri) — needs the Rust toolchain + the local Python backend
npm run tauri:dev      # build + run the desktop window (spawns the local backend)
npm run tauri:build    # produce installers (.deb/.AppImage on Linux, .msi/.exe on Windows)
```
`proxy.conf.json` forwards `/api` to the backend (port **8077**). Change both if
you move the backend. In **production/desktop** the backend serves the built SPA
same-origin (no proxy), so `/api` stays relative.

## Shape
```
src/
  index.html        dir="rtl" lang="ar", Arabic fonts (IBM Plex Sans Arabic)
  styles.css        thin global: @import "tailwindcss", .dark variant, fonts, .ltr helper
  .postcssrc.json   @tailwindcss/postcss plugin (Angular app builder picks it up)
  app/
    app.config.ts   providers: HttpClient, animations, PrimeNG theme (neutral preset)
    app.ts/.html    shell: brand, GPU/VRAM status, settings gear, theme toggle,
                    first-run GPU onboarding overlay, <router-outlet>, toast
    app.routes.ts   '' → projects, 'models', 'settings', 'projects/:id' → workspace (lazy)
    core/
      api.ts        ONE typed gateway (HTTP + WS + settings/onboard)
      types.ts      interfaces mirroring backend schemas (SystemInfo, GpuInfo, AppSettings)
    features/<name>/<name>.ts   standalone component (inline Tailwind template) + CLAUDE.md
  src-tauri/        Tauri 2 desktop shell (spawns the backend, loads 127.0.0.1:8077)
```

## Styling (Tailwind v4 + PrimeNG)
- **Tailwind drives layout/spacing/colour; PrimeNG provides the components.** No
  custom design system, no glassmorphism. Components use inline `template` with
  Tailwind utility classes and **no `styles:` array**.
- `styles.css` declares the cascade layer order `@layer theme, base, primeng,
  components, utilities;` (PrimeNG below Tailwind utilities so utilities win, above
  Tailwind base) and `@custom-variant dark` to match PrimeNG's `darkModeSelector:
  '.dark'`. The PrimeNG preset (`app.config.ts`) sets the same layer order.
- Dark mode is class-based (`.dark` on `<html>`); default is light. `app.ts` owns
  the toggle + `localStorage`; the Settings page mirrors it.
- **Shared vocabulary** (keep components consistent): cards
  `rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900`;
  muted `text-neutral-500 dark:text-neutral-400`; accent is **blue**
  (`text-blue-600 dark:text-blue-400`, `bg-blue-600` buttons); thin borders, no heavy
  shadows. Active/selected uses a blue ring (`ring-1 ring-blue-400/40`).

## Conventions
- **One API service** (`core/api.ts`); inject it, don't sprinkle `HttpClient`.
- Components use `signal()` for state, `inject()` for deps, `@Input()` for ids
  (route params bind via `withComponentInputBinding`).
- RTL is the default; never assume LTR. Use **logical** utilities (`ps-*`, `pe-*`,
  `ms-*`, `me-*`, `text-start`, `ms-auto`). Wrap Latin/technical snippets in
  `code.ltr` (the `.ltr`/`.mono` helper is still defined globally in `styles.css`).
- PrimeNG `severity="warn"` (not "warning"), `contrast`, etc. (v20 naming).
- If you need a structural directive in a template (`[ngClass]`, `*ngIf`-style),
  import it into the component's `imports:` (e.g. `NgClass` from `@angular/common`).

## Design language
Minimal, calm, Notion-like: neutral greys, generous whitespace, thin borders, a
single blue accent, content-first. Respect `prefers-reduced-motion`.
