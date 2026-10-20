import { Pipe, inject, type PipeTransform } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { formatCompact } from './format';

@Pipe({ name: 'compact', pure: false })
export class CompactPipe implements PipeTransform {
  private readonly locale = inject(LocaleStore);

  transform(value: number): string {
    return formatCompact(value, this.locale.locale());
  }
}
