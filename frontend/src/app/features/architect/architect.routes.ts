import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { architectGuard } from './guards/architect.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { ArchitectStore } from './state/architect.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [architectGuard],
    providers: [ArchitectStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/architect/architect').then((m) => m.ArchitectPage),
  },
];
