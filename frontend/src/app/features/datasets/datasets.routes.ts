import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { datasetsGuard } from './guards/datasets.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { DatasetsStore } from './state/datasets.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [datasetsGuard],
    providers: [DatasetsStore, provideTranslations(en, ar)],
    children: [
      {
        path: '',
        canActivate: [datasetsGuard],
        loadComponent: () => import('./pages/datasets/datasets').then((m) => m.DatasetsPage),
      },
      {
        path: ':id',
        canActivate: [datasetsGuard],
        loadComponent: () => import('./pages/dataset/dataset').then((m) => m.DatasetPage),
      },
    ],
  },
];
