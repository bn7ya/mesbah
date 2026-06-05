# frontend/ — Angular 20 + PrimeNG, RTL glass UI

Standalone components, signals, no NgModules. PrimeNG 20 + `@primeuix/themes`
(Aura preset tuned teal→violet). The whole app is **RTL Arabic**; technical terms
stay English.

## Run / verify
```bash
npm install
npm start          # http://localhost:4200, proxies /api (+ WS) → :8077
npm run build      # must be warning-clean
```
`proxy.conf.json` forwards `/api` to the backend (port **8077**). Change both if
you move the backend.

## Shape
```
src/
  index.html        dir="rtl" lang="ar", Arabic fonts (IBM Plex Sans Arabic)
  styles.scss       design system: aurora bg, .glass tokens, PrimeNG overrides
  app/
    app.config.ts   providers: HttpClient, animations, PrimeNG theme, Message/Confirm
    app.ts/.html    glass shell: brand, GPU/VRAM status, <router-outlet>, toast
    app.routes.ts   '' → projects, 'projects/:id' → workspace (lazy)
    core/
      api.ts        ONE typed gateway (HTTP + trainingSocket WS)
      types.ts      interfaces mirroring backend schemas
    features/<name>/<name>.ts   standalone component (inline template + styles) + CLAUDE.md
```

## Conventions
- **One API service** (`core/api.ts`); inject it, don't sprinkle `HttpClient`.
- Components use `signal()` for state, `inject()` for deps, `@Input()` for ids
  (route params bind via `withComponentInputBinding`).
- Inline `template`/`styles` per component (cohesive, glass styling is local).
- Use the global `.glass` / `.text-grad` / spacing utilities from `styles.scss`;
  use CSS vars (`--accent`, `--glass-bg`, `--radius-*`) — don't hardcode colors.
- RTL is the default; never assume LTR. Wrap Latin/technical snippets in `code.ltr`.
- PrimeNG `severity="warn"` (not "warning"), `contrast`, etc. (v20 naming).

## Design language ("emotional / human / Jony-Ive")
Calm aurora depth, frosted glass panels, generous spacing, large radii, soft
motion (respect `prefers-reduced-motion`), minimal chrome — content first.
