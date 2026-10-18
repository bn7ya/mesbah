import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { LocaleStore } from '@core/i18n/locale.store';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, TranslatePipe],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  private readonly locale = inject(LocaleStore);
  private readonly document = inject(DOCUMENT);

  readonly direction = this.locale.direction;

  skipToContent(event: Event): void {
    event.preventDefault();
    this.document.getElementById('main')?.focus();
  }
}
