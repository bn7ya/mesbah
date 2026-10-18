import { ChangeDetectionStrategy, Component, Injector, effect, inject, input, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { formatNumber } from '@shared/format/format';
import { Term } from '@shared/term/term';
import { DatasetConversation } from '../../components/conversation/conversation';
import { IMPORT_FAILURES, type Dataset, type EditDialogData, type Mapping } from '../../data/datasets.types';
import { DatasetEditDialog } from '../../dialogs/dataset-edit/dataset-edit';
import { DatasetsStore } from '../../state/datasets.store';

@Component({
  selector: 'app-dataset-page',
  imports: [
    BytesPipe,
    DatasetConversation,
    MatButton,
    MatIcon,
    MatPaginator,
    MatProgressBar,
    RouterLink,
    Term,
    TranslatePipe,
  ],
  templateUrl: './dataset.html',
  styleUrl: './dataset.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DatasetPage {
  private readonly store = inject(DatasetsStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly router = inject(Router);
  private readonly locale = inject(LocaleStore);

  readonly id = input.required<string>();

  readonly dataset = this.store.opened;
  readonly openError = this.store.openError;
  readonly rows = this.store.rows;
  readonly rowsIndex = this.store.rowsIndex;
  readonly rowsSize = this.store.rowsSize;
  readonly rowsLoading = this.store.rowsLoading;
  readonly rowsError = this.store.rowsError;
  readonly canWrite = this.store.canWrite;
  readonly expert = inject(UiModeStore).expert;

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.store.open(id));
    });
    this.store.watchOpened().pipe(takeUntilDestroyed()).subscribe();
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  when(value: string): string {
    const locale = this.locale.locale() === 'ar' ? 'ar-u-nu-latn' : 'en';
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
  }

  usedColumns(mapping: Mapping): string[] {
    return [mapping.conversation, mapping.system, mapping.prompt, mapping.input, mapping.reply, mapping.thinking, mapping.text]
      .filter((column) => column !== '');
  }

  failureKey(dataset: Dataset): string {
    const known = IMPORT_FAILURES.includes(dataset.error_code) ? dataset.error_code : 'unknown';
    return `datasets.library.failure.${known}`;
  }

  turnPage(event: PageEvent): void {
    void this.store.loadRows(event.pageIndex, event.pageSize);
  }

  reloadRows(): void {
    void this.store.loadRows();
  }

  async edit(dataset: Dataset): Promise<void> {
    const reference = this.dialog.open<DatasetEditDialog, EditDialogData, boolean>(DatasetEditDialog, {
      injector: this.injector,
      data: { dataset },
      width: '32rem',
      maxWidth: '95vw',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('datasets.saved');
    }
  }

  async remove(dataset: Dataset): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'datasets.remove.title',
      bodyKey: 'datasets.remove.body',
      confirmKey: 'datasets.remove.confirm',
      values: { name: dataset.name },
      destructive: true,
    });
    if (confirmed && (await this.store.remove(dataset))) {
      this.report('datasets.removed');
      await this.router.navigate(['/datasets']);
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
