import type { Role } from '@core/auth/roles.types';

export interface NavItem {
  readonly path: string;
  readonly labelKey: string;
  readonly icon: string;
  readonly role: Role;
}
