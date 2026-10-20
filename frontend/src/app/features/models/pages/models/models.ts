import { ChangeDetectionStrategy, Component, Injector, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { EmptyState } from '@shared/empty-state/empty-state';
import { FitVerdict } from '@shared/fit-verdict/fit-verdict';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { Note } from '@shared/note/note';
import { Status } from '@shared/status/status';
import {
  DOWNLOAD_FAILURES,
  HUB_TASKS,
  type HubResult,
  type HubTask,
  type InspectionDialogData,
  type LibraryModel,
} from '../../data/models.types';
import { ModelDetailsDialog } from '../../dialogs/model-details/model-details';
import { ModelsStore } from '../../state/models.store';

@Component({
  selector: 'app-models-page',
  imports: [
    BytesPipe,
    CompactPipe,
    EmptyState,
    FitVerdict,
    FormsModule,
    MatButton,
    MatButtonToggle,
    MatButtonToggleGroup,
    MatCard,
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
    TranslatePipe,
  ],
  templateUrl: './models.html',
  styleUrl: './models.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModelsPage {
  private readonly store = inject(ModelsStore);
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

  readonly tasks = HUB_TASKS;

  readonly searchText = signal('');
  readonly task = signal<HubTask>('text-generation');

  readonly searchBlank = computed(() => this.searchText().trim() === '');
  readonly popular = computed(() => this.hubQuery().search === '');
  readonly libraryEmpty = computed(() => this.page().results.length === 0 && !this.loading() && this.error() === null);
  readonly paged = computed(() => this.page().count > this.pageSize());

  constructor() {
    void this.store.load();
    this.store.watchDownloads().pipe(takeUntilDestroyed()).subscribe();
  }

  isWorking(model: LibraryModel): boolean {
    return this.store.working().includes(model.id);
  }

  percent(model: LibraryModel): number {
    if (model.size_bytes <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((model.downloaded_bytes / model.size_bytes) * 100));
  }

  failureKey(model: LibraryModel): string {
    const known = DOWNLOAD_FAILURES.includes(model.error_code) ? model.error_code : 'unknown';
    return `models.library.failure.${known}`;
  }

  turnPage(event: PageEvent): void {
    void this.store.load(event.pageIndex, event.pageSize);
  }

  submitSearch(): void {
    this.store.search({ search: this.searchText(), task: this.task() });
  }

  chooseTask(task: HubTask): void {
    this.task.set(task);
    this.submitSearch();
  }

  searchAgain(): void {
    this.store.searchAgain();
  }

  async showDetails(result: HubResult): Promise<void> {
    const reference = this.dialog.open<ModelDetailsDialog, InspectionDialogData, boolean>(ModelDetailsDialog, {
      injector: this.injector,
      data: { repo: result.repo_id },
      width: '35rem',
      maxWidth: '95vw',
      autoFocus: 'dialog',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('models.added');
    }
  }

  async cancel(model: LibraryModel): Promise<void> {
    if (await this.store.cancel(model)) {
      this.report('models.cancelled');
    }
  }

  async retry(model: LibraryModel): Promise<void> {
    if (await this.store.retry(model)) {
      this.report('models.retried');
    }
  }

  async remove(model: LibraryModel): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'models.remove.title',
      bodyKey: model.origin === 'trained' ? 'models.remove.bodyTrained' : 'models.remove.body',
      confirmKey: 'models.remove.confirm',
      values: { name: model.repo_id },
      destructive: true,
    });
    if (confirmed && (await this.store.remove(model))) {
      this.report('models.removed');
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
