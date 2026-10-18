import type { ProjectTab } from './data/projects.types';

export const PROJECT_TABS: readonly ProjectTab[] = [
  { path: '', labelKey: 'projects.tabs.overview', icon: 'fa-sliders', role: 'viewers' },
  { path: 'versions', labelKey: 'projects.tabs.versions', icon: 'fa-code-branch', role: 'viewers' },
];
