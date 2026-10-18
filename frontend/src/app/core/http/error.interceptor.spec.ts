import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

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
        provideRouter([]),
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

  it('falls back to the server message for an unknown code', async () => {
    const error = await fail('something_else', 'Server prose');

    expect(error.message).toBe('Server prose');
  });

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
});
