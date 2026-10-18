import { Pipe, inject, type PipeTransform } from '@angular/core';

import { LocaleStore } from './locale.store';

@Pipe({ name: 't', pure: false })
export class TranslatePipe implements PipeTransform {
  private readonly locale = inject(LocaleStore);

  transform(key: string, values?: Readonly<Record<string, string | number>>): string {
    return this.locale.translate(key, values);
  }
}
