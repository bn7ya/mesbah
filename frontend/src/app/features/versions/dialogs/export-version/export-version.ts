import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatRadioButton, MatRadioGroup } from '@angular/material/radio';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { Term } from '@shared/term/term';
import {
  EXPORT_FORMATS,
  EXPORT_QUALITIES,
  type ExportChoice,
  type ExportFormat,
  type ExportQuality,
  type NewExport,
  type VersionDialogData,
} from '../../data/versions.types';
import { VersionsStore } from '../../state/versions.store';
import { versionLabel } from '../../state/version-label';

@Component({
  selector: 'app-export-version',
  imports: [
    BytesPipe,
    MatButton,
    MatCard,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatIcon,
    MatRadioButton,
    MatRadioGroup,
    Term,
    TranslatePipe,
  ],
  templateUrl: './export-version.html',
  styleUrl: './export-version.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExportVersionDialog {
  private readonly store = inject(VersionsStore);
  private readonly reference = inject<MatDialogRef<ExportVersionDialog, boolean>>(MatDialogRef);

  readonly data = inject<VersionDialogData>(MAT_DIALOG_DATA);
  readonly label = versionLabel(this.data.version, inject(LocaleStore));

  readonly qualities = EXPORT_QUALITIES;

  readonly choices: readonly ExportChoice[] = EXPORT_FORMATS.map((format) => ({
    format,
    blocker: format !== 'gguf' && this.data.version.kind !== 'lora' ? 'versions.export.noChange' : null,
  }));

  readonly format = signal<ExportFormat>(this.choices.find((choice) => choice.blocker === null)?.format ?? 'gguf');
  readonly quality = signal<ExportQuality>('f16');
  readonly busy = signal(false);
  readonly failure = signal<ApiError | null>(null);

  async start(): Promise<void> {
    const request: NewExport =
      this.format() === 'gguf' ? { format: 'gguf', out_type: this.quality() } : { format: this.format() };
    this.busy.set(true);
    this.failure.set(null);
    const failure = await this.store.createExport(this.data.version, request);
    this.busy.set(false);
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }
}
