import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { errorInterceptor } from '@core/http/error.interceptor';
import type { Identity } from '../data/auth.types';
import { AuthStore } from './auth.store';

const IDENTITY: Identity = {
  id: 1,
  username: 'sara',
  email: 'sara@example.com',
  first_name: 'Sara',
  last_name: 'Hassan',
  is_staff: false,
  is_superuser: false,
  groups: ['members'],
  permissions: ['orders.add_order'],
};

const settle = (): Promise<void> => new Promise<void>((resolve) => queueMicrotask(resolve));

describe('AuthStore', () => {
  let store: AuthStore;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    store = TestBed.inject(AuthStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    TestBed.resetTestingModule();
  });

  it('starts unresolved, so guards do not act before /me/ answers', () => {
    expect(store.resolved()).toBe(false);
    expect(store.isAuthenticated()).toBe(false);
  });

  it('holds the identity after restoring a session', async () => {
    const restoring = store.restore();
    http.expectOne('/api/auth/me/').flush(IDENTITY);
    await restoring;

    expect(store.resolved()).toBe(true);
    expect(store.isAuthenticated()).toBe(true);
    expect(store.groups()).toEqual(['members']);
  });

  it('treats a 403 from /me/ as "signed out", not as an error', async () => {
    const restoring = store.restore();
    http.expectOne('/api/auth/me/').flush(null, { status: 403, statusText: 'Forbidden' });
    await restoring;

    expect(store.resolved()).toBe(true);
    expect(store.isAuthenticated()).toBe(false);
    expect(store.error()).toBeNull();
  });

  it('primes the CSRF cookie before posting credentials', async () => {
    const signingIn = store.signIn({ username: 'sara', password: 'secret' });

    http.expectOne('/api/auth/csrf/').flush(null);
    await settle();

    const login = http.expectOne('/api/auth/login/');
    expect(login.request.method).toBe('POST');
    login.flush(IDENTITY);

    await expect(signingIn).resolves.toBe(true);
    expect(store.busy()).toBe(false);
  });

  it('keeps the failure message when signing in is refused', async () => {
    const signingIn = store.signIn({ username: 'sara', password: 'wrong' });

    http.expectOne('/api/auth/csrf/').flush(null);
    await settle();

    http.expectOne('/api/auth/login/').flush(
      { error: { code: 'authentication_failed', message: "That username and password don't match an account." } },
      { status: 403, statusText: 'Forbidden' },
    );

    await expect(signingIn).resolves.toBe(false);
    expect(store.error()?.message).toContain("don't match");
    expect(store.isAuthenticated()).toBe(false);
  });

  it('prefers the full name and falls back to the username', async () => {
    const restoring = store.restore();
    http.expectOne('/api/auth/me/').flush(IDENTITY);
    await restoring;

    expect(store.displayName()).toBe('Sara Hassan');
  });

  it('gives a superuser every group and every permission', async () => {
    const restoring = store.restore();
    http
      .expectOne('/api/auth/me/')
      .flush({ ...IDENTITY, is_superuser: true, groups: [], permissions: [] });
    await restoring;

    expect(store.hasGroup('managers')).toBe(true);
    expect(store.hasPermission('orders.delete_order')).toBe(true);
  });

  it('does not grant a group the user is not in', async () => {
    const restoring = store.restore();
    http.expectOne('/api/auth/me/').flush(IDENTITY);
    await restoring;

    expect(store.hasGroup('managers')).toBe(false);
    expect(store.hasAnyGroup(['managers', 'members'])).toBe(true);
  });
});
