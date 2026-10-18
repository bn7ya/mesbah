import { ChangeDetectionStrategy, Component, DestroyRef, Injector, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyState } from '@shared/empty-state/empty-state';
import { Note } from '@shared/note/note';
import { ExportItem } from '../../components/export-item/export-item';
import type { VersionDialogData } from '../../data/versions.types';
import { VersionsStore } from '../../state/versions.store';
import { versionLabel } from '../../state/version-label';
import { ExportVersionDialog } from '../export-version/export-version';

@Component({
  selector: 'app-version-exports',
  imports: [
    EmptyState,
    ExportItem,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatIcon,
    MatProgressBar,
    Note,
    TranslatePipe,
  ],
  templateUrl: './version-exports.html',
  styleUrl: './version-exports.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VersionExportsDialog {
  private readonly store = inject(VersionsStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly data = inject<VersionDialogData>(MAT_DIALOG_DATA);
  readonly label = versionLabel(this.data.version, this.locale);

  readonly exports = this.store.exports;
  readonly loaded = this.store.exportsLoaded;
  readonly loading = this.store.exportsLoading;
  readonly loadFailure = this.store.exportsLoadError;
  readonly error = this.store.exportsError;
  readonly canWrite = this.store.canWrite;

  readonly empty = computed(() => this.loaded() && this.exports().length === 0 && !this.loading());

  constructor() {
    this.store.showExports(this.data.version.id);
    this.store.watchExports().pipe(takeUntilDestroyed()).subscribe();
    inject(DestroyRef).onDestroy(() => this.store.forgetExports());
  }

  tryAgain(): void {
    this.store.reloadExports();
  }

  async newExport(): Promise<void> {
    const reference = this.dialog.open<ExportVersionDialog, VersionDialogData, boolean>(ExportVersionDialog, {
      injector: this.injector,
      data: { version: this.data.version },
      width: '40rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.snackBar.open(this.locale.translate('versions.export.started'), undefined, { duration: 4000 });
    }
  }
}
