import { ChangeDetectionStrategy, Component, booleanAttribute, input } from '@angular/core';
import { MatIcon } from '@angular/material/icon';

import type { StatusTone } from './status.types';

@Component({
  selector: 'app-status',
  imports: [MatIcon],
  templateUrl: './status.html',
  styleUrl: './status.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Status {
  readonly icon = input.required<string>();
  readonly tone = input<StatusTone>('neutral');
  readonly prominent = input(false, { transform: booleanAttribute });
}
