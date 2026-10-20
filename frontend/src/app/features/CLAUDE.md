# features

One directory per page, mirroring one Django app under `backend/apps/` by the
same name (rule 13). Nothing here yet — the first slice creates the first one.

## The shape

```
features/<feature>/
  <feature>.routes.ts          lazy entry point, providers, guard
  guards/<feature>.guard.ts     rule 11 — every route has one
  pages/<page>/<page>.ts        standalone, OnPush
  pages/<page>/<page>.html      rule 7 — never inline
  pages/<page>/<page>.scss      rule 12 — tokens only, no raw px
  state/<feature>.store.ts      signals; provided by the route, not root
  data/<feature>.api.ts         one method per endpoint; the only HttpClient
  data/<feature>.types.ts       mirrors the backend contract
  i18n/en.json
  i18n/ar.json
  CLAUDE.md                     rule 3 — the Stop hook blocks without it
```

## The route

```ts
import type { Routes } from '@angular/router';
import { provideTranslations } from '@core/i18n/provide-translations';
import { groupGuard } from '@core/auth/guards/auth.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { OrdersStore } from './state/orders.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [groupGuard('managers')],
    providers: [OrdersStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/orders/orders').then((m) => m.OrdersPage),
  },
];
```

Then one lazy entry in `app.routes.ts`:

```ts
{
  path: 'orders',
  loadChildren: () => import('@features/orders/orders.routes').then((m) => m.routes),
}
```

The store is in the route's `providers`, not `providedIn: 'root'` — feature
state should die with the page.

## What each feature's CLAUDE.md should say

What the page is for, its route and guard, its Django counterpart and endpoints,
the store's signals and which are `computed`, and any decision a future session
would otherwise re-litigate. Not a file listing — the files are right there.

And a `## Classes and methods` section: each class, component, store, api and guard, and
each public method, in a line or two of what it is for — abstractly, not how it does it.
It is the one place the module is described; the code itself carries almost no comments
(rule 31). Change a method's purpose and this section changes in the same commit.
