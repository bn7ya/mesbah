import { inject } from '@angular/core';
import { Router, type ActivatedRouteSnapshot, type CanActivateFn, type RouterStateSnapshot, type UrlTree } from '@angular/router';

import { AuthStore } from '../state/auth.store';

async function ensureSignedIn(state: RouterStateSnapshot): Promise<true | UrlTree> {
  const auth = inject(AuthStore);
  const router = inject(Router);

  if (!auth.resolved()) {
    await auth.restore();
  }

  if (auth.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/sign-in'], { queryParams: { next: state.url } });
}

export const authGuard: CanActivateFn = (_route: ActivatedRouteSnapshot, state: RouterStateSnapshot) =>
  ensureSignedIn(state);

export const guestGuard: CanActivateFn = async () => {
  const auth = inject(AuthStore);
  const router = inject(Router);

  if (!auth.resolved()) {
    await auth.restore();
  }

  if (auth.isAuthenticated()) {
    return router.createUrlTree(['/']);
  }
  return (await auth.setupNeeded()) ? router.createUrlTree(['/setup']) : true;
};

export const setupGuard: CanActivateFn = async () => {
  const auth = inject(AuthStore);
  const router = inject(Router);

  return (await auth.setupNeeded()) ? true : router.createUrlTree(['/sign-in']);
};

export function groupGuard(...groups: readonly string[]): CanActivateFn {
  return async (_route: ActivatedRouteSnapshot, state: RouterStateSnapshot) => {
    const auth = inject(AuthStore);
    const router = inject(Router);

    const signedIn = await ensureSignedIn(state);
    if (signedIn !== true) {
      return signedIn;
    }

    return auth.hasAnyGroup(groups) ? true : router.createUrlTree(['/forbidden']);
  };
}
