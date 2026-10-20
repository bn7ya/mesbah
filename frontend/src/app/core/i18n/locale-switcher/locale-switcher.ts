import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';

import { LocaleStore } from '../locale.store';
import type { Locale, LocaleOption } from '../locale.types';

@Component({
  selector: 'app-locale-switcher',
  imports: [MatButtonToggleGroup, MatButtonToggle],
  templateUrl: './locale-switcher.html',
  styleUrl: './locale-switcher.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LocaleSwitcher {
  private readonly locale = inject(LocaleStore);

  readonly current = this.locale.locale;

  readonly options = computed<readonly LocaleOption[]>(() => [
    { value: 'en', label: this.locale.translate('language.english') },
    { value: 'ar', label: this.locale.translate('language.arabic') },
  ]);

  readonly label = computed(() => this.locale.translate('language.label'));

  select(locale: Locale): void {
    this.locale.setLocale(locale);
  }
}
