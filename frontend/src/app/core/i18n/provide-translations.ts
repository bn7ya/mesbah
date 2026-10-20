import { ENVIRONMENT_INITIALIZER, inject, type EnvironmentProviders, type Provider } from '@angular/core';

import { LocaleStore } from './locale.store';
import type { TranslationBundle } from './locale.types';

export function provideTranslations(
  en: TranslationBundle,
  ar: TranslationBundle,
): Provider | EnvironmentProviders {
  return {
    provide: ENVIRONMENT_INITIALIZER,
    multi: true,
    useValue: () => inject(LocaleStore).register({ en, ar }),
  };
}
