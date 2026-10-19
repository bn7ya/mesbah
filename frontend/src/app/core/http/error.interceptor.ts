import { HttpErrorResponse, type HttpInterceptorFn } from '@angular/common/http';
import { Injector, inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthStore } from '@core/auth/state/auth.store';
import { LocaleStore } from '@core/i18n/locale.store';
import type { ApiError, ApiErrorResponse } from './api.types';

const SESSION_GONE: ReadonlySet<string> = new Set(['not_authenticated', 'authentication_failed']);

export const errorInterceptor: HttpInterceptorFn = (request, next) => {
  const router = inject(Router);
  const locale = inject(LocaleStore);
  const injector = inject(Injector);

  return next(request).pipe(
    catchError((response: unknown) => {
      const error = toApiError(response, locale);

      if (response instanceof HttpErrorResponse && isSessionFailure(response, error, request.url)) {
        // Asked for here, not above: AuthStore's own requests pass through this interceptor.
        injector.get(AuthStore).forget();
        void router.navigate(['/sign-in'], {
          queryParams: { next: router.url },
          replaceUrl: true,
        });
      }

      return throwError(() => error);
    }),
  );
};

function isSessionFailure(response: HttpErrorResponse, error: ApiError, url: string): boolean {
  if (url.includes('/api/auth/')) {
    return false;
  }
  return response.status === 401 || (response.status === 403 && SESSION_GONE.has(error.code));
}

function readBody(raw: unknown): ApiErrorResponse | null {
  if (typeof raw !== 'string') {
    return raw as ApiErrorResponse | null;
  }
  try {
    return JSON.parse(raw) as ApiErrorResponse | null;
  } catch {
    return null;
  }
}

function toApiError(response: unknown, locale: LocaleStore): ApiError {
  if (!(response instanceof HttpErrorResponse)) {
    return { code: 'unknown', message: locale.translate('errors.generic') };
  }

  if (response.status === 0) {
    return { code: 'network', message: locale.translate('auth.errors.unavailable') };
  }

  const body = readBody(response.error);
  if (body?.error?.message) {
    const key = `errors.${body.error.code}`;
    const translated = locale.translate(key);
    if (translated !== key) {
      return { ...body.error, message: translated };
    }
    // The server writes English only, so any other language gets the generic message.
    return locale.locale() === 'en' ? body.error : { ...body.error, message: locale.translate('errors.generic') };
  }

  return { code: 'unknown', message: locale.translate('errors.generic') };
}
