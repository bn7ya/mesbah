import type { NavItem } from './shell.types';

export const NAVIGATION: readonly NavItem[] = [
  { path: '/projects', labelKey: 'nav.projects', icon: 'fa-folder-open', role: 'viewers' },
  { path: '/models', labelKey: 'nav.models', icon: 'fa-cube', role: 'viewers' },
  { path: '/datasets', labelKey: 'nav.datasets', icon: 'fa-database', role: 'viewers' },
  { path: '/architect', labelKey: 'nav.architect', icon: 'fa-drafting-compass', role: 'viewers' },
  { path: '/engines', labelKey: 'nav.engines', icon: 'fa-server', role: 'viewers' },
  { path: '/system', labelKey: 'nav.system', icon: 'fa-microchip', role: 'viewers' },
  { path: '/members', labelKey: 'nav.members', icon: 'fa-users', role: 'admins' },
];
