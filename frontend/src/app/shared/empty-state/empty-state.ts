import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatCard } from '@angular/material/card';
import { MatIcon } from '@angular/material/icon';

@Component({
  selector: 'app-empty-state',
  imports: [MatCard, MatIcon],
  templateUrl: './empty-state.html',
  styleUrl: './empty-state.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EmptyState {
  readonly icon = input.required<string>();
  readonly heading = input.required<string>();
}
