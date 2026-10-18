import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  provideBrowserGlobalErrorListeners,
  provideZonelessChangeDetection,
  type ApplicationConfig,
} from '@angular/core';
import { MAT_ICON_DEFAULT_OPTIONS } from '@angular/material/icon';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';

import { csrfInterceptor } from '@core/http/csrf.interceptor';
import { errorInterceptor } from '@core/http/error.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),

    provideZonelessChangeDetection(),

    provideRouter(
      routes,
      withComponentInputBinding(),
      withViewTransitions(),
    ),

    provideHttpClient(withInterceptors([csrfInterceptor, errorInterceptor])),

    { provide: MAT_ICON_DEFAULT_OPTIONS, useValue: { fontSet: 'fa-solid' } },
  ],
};
