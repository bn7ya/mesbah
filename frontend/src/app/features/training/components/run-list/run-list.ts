import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyState } from '@shared/empty-state/empty-state';
import { Note } from '@shared/note/note';
import { RUN_PAGE_SIZES } from '../../data/training.types';
import { TrainingStore } from '../../state/training.store';
import { RunRow } from '../run-row/run-row';

@Component({
  selector: 'app-run-list',
  imports: [EmptyState, MatButton, MatPaginator, MatProgressBar, Note, RunRow, TranslatePipe],
  templateUrl: './run-list.html',
  styleUrl: './run-list.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunList {
  private readonly store = inject(TrainingStore);

  readonly page = this.store.runs;
  readonly pageIndex = this.store.runsPageIndex;
  readonly pageSize = this.store.runsPageSize;
  readonly loading = this.store.runsLoading;
  readonly error = this.store.runsError;
  readonly actionError = this.store.error;
  readonly canWrite = this.store.canWrite;

  readonly sizes = RUN_PAGE_SIZES;

  readonly empty = computed(() => this.page().results.length === 0 && !this.loading() && this.error() === null);
  readonly paged = computed(() => this.page().count > Math.min(...RUN_PAGE_SIZES));

  turnPage(event: PageEvent): void {
    void this.store.loadRuns(event.pageIndex, event.pageSize);
  }

  tryAgain(): void {
    void this.store.loadRuns();
  }
}
