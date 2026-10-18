import { Clipboard } from '@angular/cdk/clipboard';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CodeBlock } from '@shared/code-block/code-block';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { Status } from '@shared/status/status';
import type { StatusTone } from '@shared/status/status.types';
import {
  EXPORT_FAILURES,
  EXPORT_STATUS_ICONS,
  UNFINISHED_EXPORTS,
  type VersionExport,
} from '../../data/versions.types';
import { VersionsStore } from '../../state/versions.store';

@Component({
  selector: 'app-export-item',
  imports: [
    BytesPipe,
    CodeBlock,
    DateTimePipe,
    MatButton,
    MatCard,
    MatIcon,
    MatProgressBar,
    Status,
    TranslatePipe,
  ],
  templateUrl: './export-item.html',
  styleUrl: './export-item.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExportItem {
  private readonly store = inject(VersionsStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly clipboard = inject(Clipboard);
  private readonly locale = inject(LocaleStore);

  readonly item = input.required<VersionExport>();

  readonly canWrite = this.store.canWrite;

  readonly busy = computed(() => this.store.exportsWorking().includes(this.item().id));
  readonly unfinished = computed(() => UNFINISHED_EXPORTS.includes(this.item().status));
  readonly icon = computed(() => EXPORT_STATUS_ICONS[this.item().status]);
  readonly tone = computed<StatusTone>(() => {
    const { status } = this.item();
    return status === 'ready' ? 'ok' : status === 'failed' ? 'error' : 'neutral';
  });
  readonly downloadUrl = computed(() => this.store.downloadUrl(this.item()));

  readonly folder = computed(() => {
    const { status, downloadable, path } = this.item();
    return status === 'ready' && !downloadable && path !== '';
  });

  readonly failureKey = computed<string | null>(() => {
    const { status, error_code } = this.item();
    if (status !== 'failed') {
      return null;
    }
    return `versions.exports.failure.${EXPORT_FAILURES.includes(error_code) ? error_code : 'failed'}`;
  });

  copyPath(): void {
    if (this.clipboard.copy(this.item().path)) {
      this.report('versions.exports.pathCopied');
    }
  }

  async remove(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'versions.exports.removeTitle',
      bodyKey: 'versions.exports.removeBody',
      confirmKey: 'versions.exports.remove',
      destructive: true,
    });
    if (confirmed && (await this.store.removeExport(this.item()))) {
      this.report('versions.exports.removed');
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
