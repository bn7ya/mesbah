import type { NavItem } from './shell.types';

export const NAVIGATION: readonly NavItem[] = [
  { path: '/system', labelKey: 'nav.system', icon: 'fa-microchip', role: 'viewers' },
  { path: '/members', labelKey: 'nav.members', icon: 'fa-users', role: 'admins' },
];
