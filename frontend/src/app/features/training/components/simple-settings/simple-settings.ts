import { ChangeDetectionStrategy, Component, computed, inject, input, model } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatIcon } from '@angular/material/icon';
import { MatSlider, MatSliderThumb } from '@angular/material/slider';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber, formatSignificant } from '@shared/format/format';
import { Term } from '@shared/term/term';
import {
  EPOCH_RANGE,
  RANK_PRESETS,
  RATE_PRESETS,
  type Hyperparams,
  type LoraRank,
} from '../../data/training.types';
import { expertChanged, resetExpert } from '../../state/train-settings';

@Component({
  selector: 'app-simple-settings',
  imports: [MatButton, MatButtonToggle, MatButtonToggleGroup, MatIcon, MatSlider, MatSliderThumb, Term, TranslatePipe],
  templateUrl: './simple-settings.html',
  styleUrl: './simple-settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SimpleSettings {
  private readonly locale = inject(LocaleStore);

  readonly settings = model.required<Hyperparams>();
  readonly defaults = input.required<Hyperparams>();
  readonly disabled = input(false);

  readonly epochRange = EPOCH_RANGE;
  readonly rankPresets = RANK_PRESETS;
  readonly ratePresets = RATE_PRESETS;

  readonly epochs = computed(() => formatNumber(this.settings().epochs, this.locale.locale(), 1));
  readonly rank = computed(() => formatNumber(this.settings().lora_rank, this.locale.locale()));
  readonly rate = computed(() => formatSignificant(this.settings().learning_rate, this.locale.locale(), 3));

  readonly rankChosen = computed(() => RANK_PRESETS.find((preset) => preset.value === this.settings().lora_rank)?.value ?? null);
  readonly rateChosen = computed(() => RATE_PRESETS.find((preset) => preset.value === this.settings().learning_rate)?.value ?? null);
  readonly changed = computed(() => expertChanged(this.settings(), this.defaults()));

  setEpochs(value: number): void {
    this.settings.update((current) => ({ ...current, epochs: value }));
  }

  setRank(value: LoraRank): void {
    this.settings.update((current) => ({ ...current, lora_rank: value }));
  }

  setRate(value: number): void {
    this.settings.update((current) => ({ ...current, learning_rate: value }));
  }

  resetExpert(): void {
    this.settings.update((current) => resetExpert(current, this.defaults()));
  }
}
