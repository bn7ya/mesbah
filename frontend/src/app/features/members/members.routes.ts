import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { membersGuard } from './guards/members.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { MembersStore } from './state/members.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [membersGuard],
    providers: [MembersStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/members/members').then((m) => m.MembersPage),
  },
];
