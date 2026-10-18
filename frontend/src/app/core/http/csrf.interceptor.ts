import { type HttpInterceptorFn } from '@angular/common/http';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);
const COOKIE_NAME = 'csrftoken';
const HEADER_NAME = 'X-CSRFToken';

export const csrfInterceptor: HttpInterceptorFn = (request, next) => {
  if (SAFE_METHODS.has(request.method)) {
    return next(request);
  }

  const token = readCookie(COOKIE_NAME);
  if (!token) {
    return next(request);
  }

  return next(request.clone({ setHeaders: { [HEADER_NAME]: token } }));
};

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split('; ')) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return null;
}
