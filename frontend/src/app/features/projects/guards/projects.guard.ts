import type { CanActivateFn } from '@angular/router';

import { roleGuard } from '@core/auth/roles';

export const projectsGuard: CanActivateFn = roleGuard('viewers');
