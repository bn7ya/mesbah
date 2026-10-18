import { Pipe, inject, type PipeTransform } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { formatBytes } from './format';

@Pipe({ name: 'bytes', pure: false })
export class BytesPipe implements PipeTransform {
  private readonly locale = inject(LocaleStore);

  transform(bytes: number): string {
    return formatBytes(bytes, this.locale.locale());
  }
}
