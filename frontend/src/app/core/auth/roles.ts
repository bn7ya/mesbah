import type { CanActivateFn } from '@angular/router';

import { groupGuard } from './guards/auth.guard';
import { ROLE_LADDER, type Role } from './roles.types';

export function rolesFrom(role: Role): readonly Role[] {
  return ROLE_LADDER.slice(ROLE_LADDER.indexOf(role));
}

export function highestRole(groups: readonly string[], superuser: boolean): Role | null {
  if (superuser) {
    return 'admins';
  }
  return [...ROLE_LADDER].reverse().find((role) => groups.includes(role)) ?? null;
}

export function roleGuard(role: Role): CanActivateFn {
  return groupGuard(...rolesFrom(role));
}
