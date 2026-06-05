import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { providePrimeNG } from 'primeng/config';
import { MessageService } from 'primeng/api';
import { ConfirmationService } from 'primeng/api';
import Aura from '@primeuix/themes/aura';
import { definePreset } from '@primeuix/themes';

import { routes } from './app.routes';

/** Misbah preset — Aura tuned to the warm creamy coral accent. */
const MisbahPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#fbf1ea', 100: '#f6ddcd', 200: '#efc3a8', 300: '#e7a983',
      400: '#dd9069', 500: '#cf7d5c', 600: '#bd6a4b', 700: '#9d543b',
      800: '#7d4330', 900: '#5f3325', 950: '#3a1f16',
    },
  },
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch()),
    provideAnimationsAsync(),
    MessageService,
    ConfirmationService,
    providePrimeNG({
      ripple: true,
      theme: {
        preset: MisbahPreset,
        options: {
          darkModeSelector: '.dark',  // we run permanently dark (see app root)
          cssLayer: { name: 'primeng', order: 'primeng' },
        },
      },
    }),
  ],
};
