import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EXAMPLE_PAGE_SIZES } from '../../data/training.types';
import { TrainingStore } from '../../state/training.store';
import { ExampleCard } from '../example-card/example-card';

@Component({
  selector: 'app-example-list',
  imports: [ExampleCard, MatButton, MatCard, MatIcon, MatPaginator, MatProgressBar, RouterLink, TranslatePipe],
  templateUrl: './example-list.html',
  styleUrl: './example-list.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExampleList {
  private readonly store = inject(TrainingStore);

  readonly projectId = this.store.projectId;
  readonly page = this.store.examples;
  readonly pageIndex = this.store.examplesPageIndex;
  readonly pageSize = this.store.examplesPageSize;
  readonly loading = this.store.examplesLoading;
  readonly error = this.store.examplesError;

  readonly sizes = EXAMPLE_PAGE_SIZES;

  readonly empty = computed(() => this.page().count === 0 && !this.loading() && this.error() === null);
  readonly paged = computed(() => this.page().count > Math.min(...EXAMPLE_PAGE_SIZES));

  turnPage(event: PageEvent): void {
    void this.store.loadExamples(event.pageIndex, event.pageSize);
  }

  tryAgain(): void {
    void this.store.loadExamples();
  }
}
