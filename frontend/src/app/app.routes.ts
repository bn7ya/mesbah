import type { Routes } from '@angular/router';

import { authGuard, guestGuard, setupGuard } from '@core/auth/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'sign-in',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('@core/auth/pages/sign-in/sign-in').then((m) => m.SignInPage),
  },
  {
    path: 'setup',
    canActivate: [setupGuard],
    loadComponent: () => import('@core/auth/pages/setup/setup').then((m) => m.SetupPage),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('@core/shell/shell').then((m) => m.Shell),
    children: [
      {
        path: '',
        pathMatch: 'full',
        // No guard: the router rejects canActivate beside redirectTo (NG04014).
        redirectTo: 'projects',
      },
      {
        path: 'projects',
        pathMatch: 'full',
        loadChildren: () => import('@features/projects/projects.routes').then((m) => m.routes),
      },
      {
        path: 'projects/:projectId',
        loadChildren: async () => {
          const { projectFrame } = await import('@features/projects/projects.routes');
          return projectFrame([
            {
              path: 'versions',
              loadChildren: () => import('@features/versions/versions.routes').then((m) => m.routes),
            },
          ]);
        },
      },
      {
        path: 'models',
        loadChildren: () => import('@features/models/models.routes').then((m) => m.routes),
      },
      {
        path: 'system',
        loadChildren: () => import('@features/system/system.routes').then((m) => m.routes),
      },
      {
        path: 'members',
        loadChildren: () => import('@features/members/members.routes').then((m) => m.routes),
      },
      {
        path: 'forbidden',
        canActivate: [authGuard],
        data: { titleKey: 'errors.forbidden', bodyKey: 'errors.forbiddenBody' },
        loadComponent: () =>
          import('@shared/status-page/status-page').then((m) => m.StatusPage),
      },
      {
        path: '**',
        canActivate: [authGuard],
        data: { titleKey: 'errors.notFound', bodyKey: 'errors.notFoundBody' },
        loadComponent: () =>
          import('@shared/status-page/status-page').then((m) => m.StatusPage),
      },
    ],
  },
];
