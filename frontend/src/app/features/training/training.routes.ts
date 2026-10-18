import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { trainingGuard } from './guards/training.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { RunStore } from './state/run.store';
import { TrainingStore } from './state/training.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [trainingGuard],
    providers: [provideTranslations(en, ar)],
    children: [
      {
        path: '',
        canActivate: [trainingGuard],
        providers: [TrainingStore],
        loadComponent: () => import('./pages/training/training').then((m) => m.TrainingPage),
      },
      {
        path: ':runId',
        canActivate: [trainingGuard],
        providers: [RunStore],
        loadComponent: () => import('./pages/run/run').then((m) => m.RunPage),
      },
    ],
  },
];
