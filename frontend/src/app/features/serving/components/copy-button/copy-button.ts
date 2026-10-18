import { CdkCopyToClipboard } from '@angular/cdk/clipboard';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';

@Component({
  selector: 'app-copy-button',
  imports: [CdkCopyToClipboard, MatButton, MatIcon, TranslatePipe],
  templateUrl: './copy-button.html',
  styleUrl: './copy-button.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CopyButton {
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly text = input.required<string>();
  readonly what = input.required<string>();

  readonly label = computed(() => this.locale.translate('serving.copy.for', { what: this.what() }));

  report(copied: boolean): void {
    this.snackBar.open(this.locale.translate(copied ? 'serving.copy.done' : 'serving.copy.failed'), undefined, {
      duration: 4000,
    });
  }
}
