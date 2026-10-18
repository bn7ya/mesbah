import type { Locale } from '@core/i18n/locale.types';
import type { StepSample } from '../data/training.types';

const MILLISECONDS = 1000;
const MINUTE = 60;
const HOUR = 3600;

const NUMBER_LOCALES: Readonly<Record<Locale, string>> = {
  en: 'en-u-nu-latn',
  ar: 'ar-u-nu-latn',
};

export function secondsLeft(samples: readonly StepSample[], total: number): number | null {
  const oldest = samples[0];
  const newest = samples.at(-1);
  if (oldest === undefined || newest === undefined || total <= 0) {
    return null;
  }
  const steps = newest.step - oldest.step;
  const seconds = (newest.at - oldest.at) / MILLISECONDS;
  if (steps <= 0 || seconds <= 0) {
    return null;
  }
  return Math.max(0, Math.ceil(((total - newest.step) * seconds) / steps));
}

export function formatDuration(totalSeconds: number, locale: Locale): string {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const unit = (value: number, name: 'hour' | 'minute' | 'second'): string =>
    new Intl.NumberFormat(NUMBER_LOCALES[locale], { style: 'unit', unit: name, unitDisplay: 'short' }).format(value);

  if (seconds < MINUTE) {
    return unit(seconds, 'second');
  }
  if (seconds < HOUR) {
    return `${unit(Math.floor(seconds / MINUTE), 'minute')} ${unit(seconds % MINUTE, 'second')}`;
  }
  const minutes = Math.floor((seconds % HOUR) / MINUTE);
  return `${unit(Math.floor(seconds / HOUR), 'hour')} ${unit(minutes, 'minute')}`;
}
