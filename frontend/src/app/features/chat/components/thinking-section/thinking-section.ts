import { ChangeDetectionStrategy, Component, input, linkedSignal } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Term } from '@shared/term/term';
import type { ThinkingOpenSource } from '../../data/chat.types';

let nextId = 0;

@Component({
  selector: 'app-thinking-section',
  imports: [MatIcon, MatIconButton, Term, TranslatePipe],
  templateUrl: './thinking-section.html',
  styleUrl: './thinking-section.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThinkingSection {
  readonly streaming = input(false);
  readonly editing = input(false);

  readonly bodyId = `thinking-body-${nextId++}`;

  readonly open = linkedSignal<ThinkingOpenSource, boolean>({
    source: () => ({ streaming: this.streaming(), editing: this.editing() }),
    computation: (now, previous) =>
      now.streaming || now.editing || (previous !== undefined && previous.source.editing && previous.value),
  });

  toggle(): void {
    this.open.update((open) => !open);
  }
}
