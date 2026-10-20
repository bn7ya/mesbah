import type { Routes } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { projectsGuard } from './guards/projects.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { ProjectStore } from './state/project.store';
import { ProjectsStore } from './state/projects.store';

export const routes: Routes = [
  {
    path: '',
    canActivate: [projectsGuard],
    providers: [ProjectsStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/projects/projects').then((m) => m.ProjectsPage),
  },
];

export function projectFrame(tabs: Routes): Routes {
  return [
    {
      path: '',
      canActivate: [projectsGuard],
      providers: [ProjectStore, provideTranslations(en, ar)],
      loadComponent: () => import('./pages/project-frame/project-frame').then((m) => m.ProjectFrame),
      children: [
        {
          path: '',
          canActivate: [projectsGuard],
          loadComponent: () => import('./pages/project-overview/project-overview').then((m) => m.ProjectOverview),
        },
        ...tabs,
      ],
    },
  ];
}
