import { HttpErrorResponse, type HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import type { ApiError, ApiErrorResponse } from './api.types';

export const errorInterceptor: HttpInterceptorFn = (request, next) => {
  const router = inject(Router);
  const locale = inject(LocaleStore);

  return next(request).pipe(
    catchError((response: unknown) => {
      const error = toApiError(response, locale);

      if (response instanceof HttpErrorResponse && isSessionFailure(response, request.url)) {
        void router.navigate(['/sign-in'], {
          queryParams: { next: router.url },
          replaceUrl: true,
        });
      }

      return throwError(() => error);
    }),
  );
};

function isSessionFailure(response: HttpErrorResponse, url: string): boolean {
  if (response.status !== 401 && response.status !== 403) {
    return false;
  }
  return !url.includes('/api/auth/');
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
    return translated === key ? body.error : { ...body.error, message: translated };
  }

  return { code: 'unknown', message: locale.translate('errors.generic') };
}
