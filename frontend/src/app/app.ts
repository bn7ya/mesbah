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

  readonly direction = this.locale.direction;
}
