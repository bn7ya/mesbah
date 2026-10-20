import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { versionsGuard } from './guards/versions.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { VersionsStore } from './state/versions.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [versionsGuard],
    providers: [VersionsStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/versions/versions').then((m) => m.VersionsPage),
  },
];
