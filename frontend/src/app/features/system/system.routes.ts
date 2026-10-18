import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { systemGuard } from './guards/system.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { SystemStore } from './state/system.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [systemGuard],
    providers: [SystemStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/system/system').then((m) => m.SystemPage),
  },
];
