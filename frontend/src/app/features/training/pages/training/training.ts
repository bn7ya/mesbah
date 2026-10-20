import { ChangeDetectionStrategy, Component, ElementRef, computed, effect, inject, input, signal, untracked, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatCard } from '@angular/material/card';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import { ExampleList } from '../../components/example-list/example-list';
import { RunList } from '../../components/run-list/run-list';
import { TrainForm } from '../../components/train-form/train-form';
import type { TrainingView } from '../../data/training.types';
import { TrainingStore } from '../../state/training.store';

@Component({
  selector: 'app-training-page',
  imports: [
    ExampleList,
    MatButton,
    MatButtonToggle,
    MatButtonToggleGroup,
    MatCard,
    MatIcon,
    MatProgressBar,
    Note,
    RouterLink,
    RunList,
    Term,
    TrainForm,
    TranslatePipe,
  ],
  templateUrl: './training.html',
  styleUrl: './training.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrainingPage {
  private readonly store = inject(TrainingStore);
  private readonly locale = inject(LocaleStore);

  readonly projectId = input.required<string>();

  readonly canWrite = this.store.canWrite;
  readonly planLoading = this.store.planLoading;
  readonly view = signal<TrainingView>('runs');

  readonly corrections = computed(() => {
    const plan = this.store.plan();
    return plan === null ? null : formatNumber(plan.corrections, this.locale.locale());
  });
  readonly none = computed(() => this.store.plan()?.corrections === 0);
  readonly setupError = computed(() => this.store.planError() ?? this.store.versionsError() ?? this.store.datasetsError());

  private readonly views = viewChild.required<ElementRef<HTMLElement>>('views');

  constructor() {
    effect(() => {
      const id = this.projectId();
      untracked(() => this.store.open(id));
    });
    effect(() => {
      this.projectId();
      if (this.view() === 'examples') {
        untracked(() => void this.store.loadExamples());
      }
    });
    this.store.watchRuns().pipe(takeUntilDestroyed()).subscribe();
  }

  choose(view: TrainingView): void {
    this.view.set(view);
  }

  seeExamples(): void {
    this.view.set('examples');
    this.views().nativeElement.scrollIntoView();
  }

  tryAgain(): void {
    this.store.reloadSetup();
  }
}
