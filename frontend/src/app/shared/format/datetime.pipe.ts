import { Pipe, inject, type PipeTransform } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { formatDateTime } from './format';

@Pipe({ name: 'datetime', pure: false })
export class DateTimePipe implements PipeTransform {
  private readonly locale = inject(LocaleStore);

  transform(iso: string): string {
    return formatDateTime(iso, this.locale.locale());
  }
}
