import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import type { Locale } from '@core/i18n/locale.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';

export const RIAL_SIGN = '⃄';

const FORMATS: Readonly<Record<Locale, Intl.NumberFormat>> = {
  en: new Intl.NumberFormat('en-OM-u-nu-latn', { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
  ar: new Intl.NumberFormat('ar-OM-u-nu-latn', { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
};

@Component({
  selector: 'app-money',
  imports: [TranslatePipe],
  templateUrl: './money.html',
  styleUrl: './money.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Money {
  private readonly locale = inject(LocaleStore);

  readonly amount = input.required<string | number>();

  readonly sign = RIAL_SIGN;

  readonly formatted = computed(() => FORMATS[this.locale.locale()].format(Number(this.amount())));
}
