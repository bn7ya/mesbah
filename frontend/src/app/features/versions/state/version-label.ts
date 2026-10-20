import type { LocaleStore } from '@core/i18n/locale.store';
import { versionName } from '@shared/version/version-name.pipe';
import type { Version } from '../data/versions.types';

export function versionLabel(version: Version, locale: LocaleStore): string {
  return `v${version.number} · ${versionName(version, locale)}`;
}
