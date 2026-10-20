import { Pipe, inject, type PipeTransform } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { ROOT_NUMBER, SEEDED_ROOT_NAME, type VersionLabel } from './version.types';

export function versionName(version: Pick<VersionLabel, 'number' | 'name'>, locale: LocaleStore): string {
  const seeded = version.number === ROOT_NUMBER && version.name === SEEDED_ROOT_NAME;
  return seeded ? locale.translate('version.baseName') : version.name;
}

@Pipe({ name: 'versionName', pure: false })
export class VersionNamePipe implements PipeTransform {
  private readonly locale = inject(LocaleStore);

  transform(version: Pick<VersionLabel, 'number' | 'name'>): string {
    return versionName(version, this.locale);
  }
}
