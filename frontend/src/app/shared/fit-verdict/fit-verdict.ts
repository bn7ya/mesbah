import { ChangeDetectionStrategy, Component, booleanAttribute, computed, input } from '@angular/core';

import { Status } from '../status/status';
import { FIT_ICONS, type FitKind } from './fit-verdict.types';

@Component({
  selector: 'app-fit-verdict',
  imports: [Status],
  templateUrl: './fit-verdict.html',
  styleUrl: './fit-verdict.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FitVerdict {
  readonly verdict = input.required<FitKind>();
  readonly prominent = input(false, { transform: booleanAttribute });

  readonly icon = computed(() => FIT_ICONS[this.verdict()]);
  readonly tone = computed(() => (this.verdict() === 'too_large' ? 'error' : 'neutral'));
}
