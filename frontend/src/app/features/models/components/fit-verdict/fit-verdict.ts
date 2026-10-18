import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatIcon } from '@angular/material/icon';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { FIT_ICONS, type FitVerdict as Verdict } from '../../data/models.types';

@Component({
  selector: 'app-fit-verdict',
  imports: [MatIcon, TranslatePipe],
  templateUrl: './fit-verdict.html',
  styleUrl: './fit-verdict.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FitVerdict {
  readonly verdict = input.required<Verdict>();

  readonly icon = computed(() => FIT_ICONS[this.verdict()]);
}
