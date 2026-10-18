import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatListItemLine, MatListItemTitle, MatListOption, MatSelectionList } from '@angular/material/list';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber } from '@shared/format/format';
import { NAME_MAX, type Source, type TrainDialogData, type TrainStarted } from '../../data/architect.types';
import { ArchitectStore } from '../../state/architect.store';

@Component({
  selector: 'app-train',
  imports: [
    FormsModule,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatListItemLine,
    MatListItemTitle,
    MatListOption,
    MatProgressBar,
    MatSelectionList,
    RouterLink,
    TranslatePipe,
  ],
  templateUrl: './train.html',
  styleUrl: './train.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrainDialog {
  private readonly store = inject(ArchitectStore);
  private readonly locale = inject(LocaleStore);
  private readonly reference = inject<MatDialogRef<TrainDialog, TrainStarted>>(MatDialogRef);
  private readonly matchers = new Map<string, ErrorStateMatcher>();

  readonly data = inject<TrainDialogData>(MAT_DIALOG_DATA);

  readonly sources = this.store.sources;
  readonly datasets = this.store.datasets;
  readonly loading = this.store.sourcesLoading;
  readonly loadFailure = this.store.sourcesError;
  readonly training = this.store.training;

  readonly nameMax = NAME_MAX;

  readonly name = signal(this.data.draft.name);
  readonly picked = signal<readonly string[]>([]);
  readonly pickedDatasets = signal<readonly string[]>([]);
  readonly limits = signal<Readonly<Record<string, number | null>>>({});
  readonly submitted = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly nothingAvailable = computed(
    () =>
      !this.loading() &&
      this.loadFailure() === null &&
      this.datasets().length === 0 &&
      !this.sources().some((source) => this.learnable(source)),
  );

  readonly chosenReplies = computed(() =>
    this.sources()
      .filter((source) => this.picked().includes(source.id))
      .reduce((sum, source) => sum + (source.corrections ?? 0), 0),
  );
  readonly chosenDatasets = computed(() => this.datasets().filter((dataset) => this.pickedDatasets().includes(dataset.id)));

  readonly nothingChosen = computed(() => this.picked().length === 0 && this.pickedDatasets().length === 0);
  readonly limitsInvalid = computed(() => this.chosenDatasets().some((dataset) => this.limitInvalid(dataset.id)));
  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };

  readonly canTrain = computed(
    () => !this.loading() && !this.training() && !this.nothingChosen() && !this.limitsInvalid(),
  );

  constructor() {
    void this.store.loadSources();
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  learnable(source: Source): boolean {
    return (source.corrections ?? 0) > 0;
  }

  limitInvalid(id: string): boolean {
    const value = this.limits()[id];
    return value !== null && value !== undefined && (!Number.isInteger(value) || value < 1);
  }

  limitMatcher(id: string): ErrorStateMatcher {
    let found = this.matchers.get(id);
    if (found === undefined) {
      found = { isErrorState: () => this.limitInvalid(id) };
      this.matchers.set(id, found);
    }
    return found;
  }

  setLimit(id: string, value: number | null): void {
    this.limits.update((current) => ({ ...current, [id]: value }));
  }

  loadAgain(): void {
    void this.store.loadSources();
  }

  async submit(): Promise<void> {
    this.submitted.set(true);
    this.failure.set(null);
    if (this.nameInvalid() || !this.canTrain()) {
      return;
    }
    const chosen = this.chosenDatasets().map((dataset) => ({ id: dataset.id, max_rows: this.limits()[dataset.id] ?? null }));
    const result = await this.store.train(this.data.draft, this.name().trim(), this.picked(), chosen);
    if ('started' in result) {
      this.reference.close(result.started);
    } else {
      this.failure.set(result.error);
    }
  }
}
