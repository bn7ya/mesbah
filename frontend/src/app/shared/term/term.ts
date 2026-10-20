import { CdkConnectedOverlay, CdkOverlayOrigin, type ConnectedPosition } from '@angular/cdk/overlay';
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';

import { LocaleStore } from '@core/i18n/locale.store';

const GAP = 4;

let nextId = 0;

@Component({
  selector: 'app-term',
  imports: [CdkConnectedOverlay, CdkOverlayOrigin, MatIcon, MatIconButton],
  templateUrl: './term.html',
  styleUrl: './term.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Term {
  private readonly locale = inject(LocaleStore);

  readonly key = input.required<string>();

  readonly open = signal(false);

  readonly panelId = `app-term-${nextId++}`;

  readonly word = computed(() => this.locale.translate(`glossary.${this.key()}.term`));
  readonly explanation = computed(() => this.locale.translate(`glossary.${this.key()}.explain`));
  readonly buttonLabel = computed(() => this.locale.translate('glossary.explainTerm', { term: this.word() }));

  readonly positions: ConnectedPosition[] = [
    { originX: 'start', originY: 'bottom', overlayX: 'start', overlayY: 'top', offsetY: GAP },
    { originX: 'start', originY: 'top', overlayX: 'start', overlayY: 'bottom', offsetY: -GAP },
  ];

  toggle(): void {
    this.open.update((open) => !open);
  }

  close(): void {
    this.open.set(false);
  }

  closeOnEscape(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
    }
  }
}
