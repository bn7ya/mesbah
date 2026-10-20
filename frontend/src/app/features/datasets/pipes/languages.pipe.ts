import { Pipe, inject, type PipeTransform } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';

@Pipe({ name: 'languages', pure: false })
export class LanguagesPipe implements PipeTransform {
  private readonly locale = inject(LocaleStore);

  transform(codes: readonly string[]): string {
    const locale = this.locale.locale();
    const names = codes.map((code) => languageName(code, locale));
    return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(names);
  }
}

function languageName(code: string, locale: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: 'language' }).of(code) ?? code;
  } catch {
    return code;
  }
}
