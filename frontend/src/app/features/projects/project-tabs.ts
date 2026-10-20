import type { ProjectTab } from './data/projects.types';

export const PROJECT_TABS: readonly ProjectTab[] = [
  { path: '', labelKey: 'projects.tabs.overview', icon: 'fa-sliders', role: 'viewers' },
  { path: 'chat', labelKey: 'projects.tabs.chat', icon: 'fa-comments', role: 'viewers' },
  { path: 'training', labelKey: 'projects.tabs.training', icon: 'fa-graduation-cap', role: 'viewers' },
  { path: 'versions', labelKey: 'projects.tabs.versions', icon: 'fa-code-branch', role: 'viewers' },
];
