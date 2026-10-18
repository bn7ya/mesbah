export type Locale = 'en' | 'ar';

export type Direction = 'ltr' | 'rtl';

export interface TranslationBundle {
  readonly [key: string]: string | TranslationBundle;
}

export interface TranslationSet {
  readonly en: TranslationBundle;
  readonly ar: TranslationBundle;
}

export interface LocaleOption {
  readonly value: Locale;
  readonly label: string;
}

export const LOCALES: readonly Locale[] = ['en', 'ar'];

export const DIRECTION: Readonly<Record<Locale, Direction>> = {
  en: 'ltr',
  ar: 'rtl',
};
