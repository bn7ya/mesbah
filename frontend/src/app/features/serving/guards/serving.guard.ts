import type { CanActivateFn } from '@angular/router';

import { roleGuard } from '@core/auth/roles';

export const servingGuard: CanActivateFn = roleGuard('viewers');
