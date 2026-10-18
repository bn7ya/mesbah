import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatCard } from '@angular/material/card';
import { MatChip, MatChipAvatar, MatChipSet } from '@angular/material/chips';
import { MatIcon } from '@angular/material/icon';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import type { Example, Turn } from '../../data/training.types';

@Component({
  selector: 'app-example-card',
  imports: [DateTimePipe, MatCard, MatChip, MatChipAvatar, MatChipSet, MatIcon, TranslatePipe],
  templateUrl: './example-card.html',
  styleUrl: './example-card.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExampleCard {
  readonly example = input.required<Example>();

  readonly earlier = computed<readonly Turn[]>(() => this.example().messages.slice(0, -1));
  readonly learned = computed<Turn | null>(() => this.example().messages.at(-1) ?? null);
  readonly asIs = computed(() => !this.example().corrected && !this.example().thinking_corrected);
}
