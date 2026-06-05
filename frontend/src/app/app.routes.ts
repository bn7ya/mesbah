import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/projects/projects-page').then((m) => m.ProjectsPage),
    title: 'المشاريع · مِصباح',
  },
  {
    path: 'models',
    loadComponent: () => import('./features/models/models-page').then((m) => m.ModelsPage),
    title: 'النماذج · مِصباح',
  },
  {
    path: 'projects/:id',
    loadComponent: () => import('./features/workspace/workspace-page').then((m) => m.WorkspacePage),
    title: 'مساحة العمل · مِصباح',
  },
  { path: '**', redirectTo: '' },
];
