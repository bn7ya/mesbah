import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { servingGuard } from './guards/serving.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { ServingStore } from './state/serving.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [servingGuard],
    providers: [ServingStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/engines/engines').then((m) => m.EnginesPage),
  },
];
