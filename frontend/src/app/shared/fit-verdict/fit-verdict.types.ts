export type FitKind = 'fits' | 'tight' | 'too_large' | 'cpu_only' | 'unknown';

export const FIT_ICONS: Readonly<Record<FitKind, string>> = {
  fits: 'fa-circle-check',
  tight: 'fa-triangle-exclamation',
  too_large: 'fa-circle-xmark',
  cpu_only: 'fa-microchip',
  unknown: 'fa-circle-question',
};
