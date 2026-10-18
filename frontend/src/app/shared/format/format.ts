import type { Locale } from '@core/i18n/locale.types';

const NUMBER_LOCALES: Readonly<Record<Locale, string>> = {
  en: 'en-u-nu-latn',
  ar: 'ar-u-nu-latn',
};

const UNITS: readonly string[] = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

const STEP = 1024;

// Unicode isolates keep "16 GB" in reading order inside an Arabic sentence.
const LTR_START = '\u2066';
const LTR_END = '\u2069';

export function formatNumber(value: number, locale: Locale, fractionDigits = 0): string {
  return new Intl.NumberFormat(NUMBER_LOCALES[locale], {
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

export function formatBytes(bytes: number, locale: Locale): string {
  let value = Math.max(0, bytes);
  let unit = 0;
  while (value >= STEP && unit < UNITS.length - 1) {
    value /= STEP;
    unit += 1;
  }
  const digits = value < 10 && unit > 0 ? 1 : 0;
  return `${LTR_START}${formatNumber(value, locale, digits)} ${UNITS[unit]}${LTR_END}`;
}
