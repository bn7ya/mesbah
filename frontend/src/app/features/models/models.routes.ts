import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { modelsGuard } from './guards/models.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { ModelsStore } from './state/models.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [modelsGuard],
    providers: [ModelsStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/models/models').then((m) => m.ModelsPage),
  },
];
