import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Identity } from '@core/auth/data/auth.types';
import { AuthStore } from '@core/auth/state/auth.store';
import { LocaleStore } from '@core/i18n/locale.store';
import type { ApiError } from './api.types';
import { errorInterceptor } from './error.interceptor';

describe('errorInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let locale: LocaleStore;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: '**', children: [] }]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    locale = TestBed.inject(LocaleStore);
    locale.setLocale('ar');
    locale.register({ en: { errors: { sample_code: 'In English' } }, ar: { errors: { sample_code: 'بالعربية' } } });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  async function fail(code: string, message: string): Promise<ApiError> {
    const request = firstValueFrom(http.get('/api/thing/'));
    backend.expectOne('/api/thing/').flush({ error: { code, message } }, { status: 400, statusText: 'Bad Request' });
    try {
      await request;
    } catch (error) {
      return error as ApiError;
    }
    throw new Error('the request did not fail');
  }

  it('shows a known error code in the reader language', async () => {
    const error = await fail('sample_code', 'Server prose');

    expect(error).toEqual({ code: 'sample_code', message: 'بالعربية' });
  });

  it('keeps the server message for an unknown code when the reader is in English', async () => {
    locale.setLocale('en');

    const error = await fail('something_else', 'Server prose');

    expect(error).toEqual({ code: 'something_else', message: 'Server prose' });
  });

  it('shows the generic message in the reader language for an unknown code, never the server English', async () => {
    const error = await fail('something_else', 'Server prose');

    expect(error).toEqual({ code: 'something_else', message: locale.translate('errors.generic') });
    expect(error.message).not.toBe('Server prose');
    expect(error.message).not.toBe('errors.generic');
  });

  it.each(['authentication_failed', 'account_deactivated'])(
    'writes the %s sign-in refusal in the reader language, from the core bundle',
    async (code) => {
      const error = await fail(code, 'Server prose');

      expect(error.code).toBe(code);
      expect(error.message).toMatch(/[\u0600-\u06ff]/);
      expect(error.message).not.toBe(locale.translate('errors.generic'));
    },
  );

  it('reads the error of a request whose body is read as text', async () => {
    const request = firstValueFrom(http.post('/api/thing/', {}, { responseType: 'text' }));
    backend
      .expectOne('/api/thing/')
      .flush(JSON.stringify({ error: { code: 'sample_code', message: 'Server prose' } }), {
        status: 409,
        statusText: 'Conflict',
      });

    await expect(request).rejects.toEqual({ code: 'sample_code', message: 'بالعربية' });
  });

  it('does not fail on a text body that is not JSON', async () => {
    const request = firstValueFrom(http.post('/api/thing/', {}, { responseType: 'text' }));
    backend.expectOne('/api/thing/').flush('Bad gateway', { status: 502, statusText: 'Bad Gateway' });

    await expect(request).rejects.toMatchObject({ code: 'unknown' });
  });

  describe('a session the server no longer accepts', () => {
    const owner: Identity = {
      id: 1,
      username: 'owner',
      email: '',
      first_name: '',
      last_name: '',
      is_staff: true,
      is_superuser: true,
      groups: ['admins'],
      permissions: [],
    };

    async function signedIn(): Promise<AuthStore> {
      const auth = TestBed.inject(AuthStore);
      const restoring = auth.restore();
      backend.expectOne('/api/auth/me/').flush(owner);
      await restoring;
      return auth;
    }

    async function refused(url: string, status: number, code: string): Promise<void> {
      const request = firstValueFrom(http.get(url));
      backend.expectOne(url).flush({ error: { code, message: 'No' } }, { status, statusText: 'No' });
      await request.catch(() => undefined);
    }

    it.each([
      [401, 'not_authenticated'],
      [403, 'not_authenticated'],
      [403, 'authentication_failed'],
    ])('forgets who was signed in and goes to sign in on a %s %s', async (status, code) => {
      const auth = await signedIn();
      const navigate = vi.spyOn(TestBed.inject(Router), 'navigate');

      await refused('/api/projects/', status, code);

      expect(auth.isAuthenticated()).toBe(false);
      expect(navigate).toHaveBeenCalledWith(['/sign-in'], expect.objectContaining({ replaceUrl: true }));
    });

    it('stays signed in on a refusal that is about permission, not the session', async () => {
      const auth = await signedIn();
      const navigate = vi.spyOn(TestBed.inject(Router), 'navigate');

      await refused('/api/members/', 403, 'permission_denied');

      expect(auth.isAuthenticated()).toBe(true);
      expect(navigate).not.toHaveBeenCalled();
    });

    it('leaves the sign-in calls to the sign-in page', async () => {
      const auth = await signedIn();
      const navigate = vi.spyOn(TestBed.inject(Router), 'navigate');

      await refused('/api/auth/login/', 403, 'authentication_failed');

      expect(auth.isAuthenticated()).toBe(true);
      expect(navigate).not.toHaveBeenCalled();
    });
  });
});
