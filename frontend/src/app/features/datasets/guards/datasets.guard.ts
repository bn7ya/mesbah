import type { CanActivateFn } from '@angular/router';

import { roleGuard } from '@core/auth/roles';

export const datasetsGuard: CanActivateFn = roleGuard('viewers');
