import type { Routes } from '@angular/router';

import { authGuard, guestGuard } from '@core/auth/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'sign-in',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('@core/auth/pages/sign-in/sign-in').then((m) => m.SignInPage),
  },
  {
    path: 'forbidden',
    canActivate: [authGuard],
    data: { titleKey: 'errors.forbidden', bodyKey: 'errors.forbiddenBody' },
    loadComponent: () =>
      import('@shared/status-page/status-page').then((m) => m.StatusPage),
  },
  {
    path: '',
    pathMatch: 'full',
    // No guard: the router rejects canActivate beside redirectTo (NG04014).
    redirectTo: 'sign-in',
  },
  {
    path: '**',
    canActivate: [authGuard],
    data: { titleKey: 'errors.notFound', bodyKey: 'errors.notFoundBody' },
    loadComponent: () =>
      import('@shared/status-page/status-page').then((m) => m.StatusPage),
  },
];
