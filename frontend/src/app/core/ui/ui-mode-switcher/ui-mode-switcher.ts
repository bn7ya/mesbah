import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';

import { LocaleStore } from '@core/i18n/locale.store';
import { UiModeStore } from '../ui-mode.store';
import type { UiMode, UiModeOption } from '../ui-mode.types';

@Component({
  selector: 'app-ui-mode-switcher',
  imports: [MatButtonToggleGroup, MatButtonToggle],
  templateUrl: './ui-mode-switcher.html',
  styleUrl: './ui-mode-switcher.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UiModeSwitcher {
  private readonly modes = inject(UiModeStore);
  private readonly locale = inject(LocaleStore);

  readonly current = this.modes.mode;

  readonly options = computed<readonly UiModeOption[]>(() => [
    { value: 'simple', label: this.locale.translate('mode.simple') },
    { value: 'expert', label: this.locale.translate('mode.expert') },
  ]);

  readonly label = computed(() => this.locale.translate('mode.label'));

  select(mode: UiMode): void {
    this.modes.setMode(mode);
  }
}
