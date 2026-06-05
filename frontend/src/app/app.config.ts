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

/** Misbah preset — Aura tuned to the teal→violet glass accent. */
const MisbahPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eafaf8', 100: '#c5f0ea', 200: '#9fe6dc', 300: '#79dccd',
      400: '#5fd6c4', 500: '#4fd1c5', 600: '#3bb6ab', 700: '#2c9089',
      800: '#1f6f78', 900: '#134e54', 950: '#0a2f34',
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
