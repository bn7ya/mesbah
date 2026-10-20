import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { RouterLink } from '@angular/router';

import { TranslatePipe } from '@core/i18n/translate.pipe';

@Component({
  selector: 'app-status-page',
  imports: [MatButton, MatCard, RouterLink, TranslatePipe],
  templateUrl: './status-page.html',
  styleUrl: './status-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusPage {
  readonly titleKey = input.required<string>();
  readonly bodyKey = input.required<string>();
}
