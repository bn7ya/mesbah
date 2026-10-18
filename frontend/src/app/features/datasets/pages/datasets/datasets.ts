import { ChangeDetectionStrategy, Component, Injector, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionPanel, MatExpansionPanelHeader, MatExpansionPanelTitle } from '@angular/material/expansion';
import { MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { EmptyState } from '@shared/empty-state/empty-state';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { formatCompact, formatNumber } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Status } from '@shared/status/status';
import { Term } from '@shared/term/term';
import {
  IMPORT_FAILURES,
  LAYOUTS,
  MAX_UPLOAD_BYTES,
  UPLOAD_TYPES,
  type Dataset,
  type HubDataset,
  type InspectDialogData,
  type SizeRange,
} from '../../data/datasets.types';
import { DatasetInspectDialog } from '../../dialogs/dataset-inspect/dataset-inspect';
import { LanguagesPipe } from '../../pipes/languages.pipe';
import { DatasetsStore } from '../../state/datasets.store';

const SIZE_CATEGORY = /^(?:(?<min>[\d.]+[KMBT]?)<)?n(?:<(?<max>[\d.]+[KMBT]?))?$|^n>(?<over>[\d.]+[KMBT]?)$/;
const SIZE_UNITS: Readonly<Record<string, number>> = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 };

@Component({
  selector: 'app-datasets-page',
  imports: [
    BytesPipe,
    CompactPipe,
    EmptyState,
    FormsModule,
    LanguagesPipe,
    MatButton,
    MatCard,
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
    MatFormField,
    MatHint,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatPaginator,
    MatProgressBar,
    MatSuffix,
    Note,
    RouterLink,
    Status,
    Term,
    TranslatePipe,
  ],
  templateUrl: './datasets.html',
  styleUrl: './datasets.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DatasetsPage {
  private readonly store = inject(DatasetsStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly page = this.store.page;
  readonly pageIndex = this.store.pageIndex;
  readonly pageSize = this.store.pageSize;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly canWrite = this.store.canWrite;
  readonly hubQuery = this.store.hubQuery;
  readonly hubResults = this.store.hubResults;
  readonly hubLoading = this.store.hubLoading;
  readonly hubError = this.store.hubError;
  readonly uploading = this.store.uploading;
  readonly uploadProgress = this.store.uploadProgress;

  readonly layouts = LAYOUTS;
  readonly uploadTypes = UPLOAD_TYPES;
  readonly maxUpload = MAX_UPLOAD_BYTES;

  readonly searchText = signal('');
  readonly uploadFailure = signal<ApiError | null>(null);
  readonly uploadName = signal('');

  readonly popular = computed(() => this.hubQuery() === '');
  readonly libraryEmpty = computed(() => this.page().results.length === 0 && !this.loading() && this.error() === null);
  readonly paged = computed(() => this.page().count > this.pageSize());

  constructor() {
    void this.store.load();
    this.store.watchImports().pipe(takeUntilDestroyed()).subscribe();
  }

  isWorking(dataset: Dataset): boolean {
    return this.store.working().includes(dataset.id);
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  target(dataset: Dataset): number | null {
    const limits = [dataset.row_limit, dataset.source_rows].filter((value): value is number => value !== null);
    return limits.length === 0 ? null : Math.min(...limits);
  }

  percent(dataset: Dataset): number {
    const target = this.target(dataset);
    if (target === null || target <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((dataset.rows / target) * 100));
  }

  failureKey(dataset: Dataset): string {
    const known = IMPORT_FAILURES.includes(dataset.error_code) ? dataset.error_code : 'unknown';
    return `datasets.library.failure.${known}`;
  }

  sizeRange(category: string): SizeRange | null {
    const match = SIZE_CATEGORY.exec(category.trim());
    const groups = match?.groups;
    if (!groups) {
      return null;
    }
    if (groups['over']) {
      return { key: 'over', min: this.amount(groups['over']), max: '' };
    }
    if (groups['min'] && groups['max']) {
      return { key: 'between', min: this.amount(groups['min']), max: this.amount(groups['max']) };
    }
    return groups['max'] ? { key: 'under', min: '', max: this.amount(groups['max']) } : null;
  }

  turnPage(event: PageEvent): void {
    void this.store.load(event.pageIndex, event.pageSize);
  }

  submitSearch(): void {
    this.store.search(this.searchText());
  }

  searchAgain(): void {
    this.store.searchAgain();
  }

  async preview(result: HubDataset): Promise<void> {
    const reference = this.dialog.open<DatasetInspectDialog, InspectDialogData, boolean>(DatasetInspectDialog, {
      injector: this.injector,
      data: { repo: result.repo_id },
      width: '48rem',
      maxWidth: '95vw',
      autoFocus: 'dialog',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('datasets.imported');
    }
  }

  async upload(input: HTMLInputElement): Promise<void> {
    const file = input.files?.item(0) ?? null;
    input.value = '';
    if (file === null) {
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      this.uploadFailure.set({ code: 'file_too_large', message: this.locale.translate('errors.file_too_large') });
      return;
    }
    this.uploadFailure.set(null);
    const failure = await this.store.upload(file, this.uploadName().trim());
    this.uploadFailure.set(failure);
    if (failure === null) {
      this.uploadName.set('');
      this.report('datasets.uploaded');
    }
  }

  async cancel(dataset: Dataset): Promise<void> {
    if (await this.store.cancel(dataset)) {
      this.report('datasets.cancelled');
    }
  }

  async retry(dataset: Dataset): Promise<void> {
    if (await this.store.retry(dataset)) {
      this.report('datasets.retried');
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
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }

  private amount(written: string): string {
    const unit = SIZE_UNITS[written.slice(-1)] ?? 1;
    return formatCompact(Number.parseFloat(written) * unit, this.locale.locale());
  }
}
