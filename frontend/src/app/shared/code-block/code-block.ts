import { ViewportRuler } from '@angular/cdk/scrolling';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { LocaleStore } from '@core/i18n/locale.store';

@Component({
  selector: 'app-code-block',
  templateUrl: './code-block.html',
  styleUrl: './code-block.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CodeBlock {
  private readonly locale = inject(LocaleStore);
  private readonly resized = toSignal(inject(ViewportRuler).change());

  readonly code = input.required<string>();
  readonly label = input<string | null>(null);

  private readonly body = viewChild.required<ElementRef<HTMLElement>>('body');

  readonly scrolls = signal(false);

  readonly name = computed(() => this.label() ?? this.locale.translate('codeBlock.name'));

  constructor() {
    afterRenderEffect(() => {
      this.code();
      this.resized();
      const element = this.body().nativeElement;
      this.scrolls.set(element.scrollWidth > element.clientWidth);
    });
  }
}
