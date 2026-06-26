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

/** Misbah preset — Aura tuned to a calm, neutral Notion-like blue accent. */
const MisbahPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
      400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
      800: '#1e40af', 900: '#1e3a8a', 950: '#172554',
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
          darkModeSelector: '.dark',  // class-based dark mode (default light; toggle in the top bar)
          // Inject PrimeNG into the `primeng` cascade layer; styles.scss declares
          // the order so Tailwind utilities can override PrimeNG when needed.
          cssLayer: { name: 'primeng', order: 'theme, base, primeng, components, utilities' },
        },
      },
    }),
  ],
};
