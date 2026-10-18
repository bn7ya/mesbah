import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatOption, type ErrorStateMatcher } from '@angular/material/core';
import { MatDivider } from '@angular/material/divider';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSelect, MatSelectTrigger } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { formatNumber } from '@shared/format/format';
import { Term } from '@shared/term/term';
import {
  FIT_ICONS,
  NAME_MAX,
  type DatasetChoice,
  type Draft,
  type Fit,
  type Hyperparams,
  type LibraryDataset,
  type StartVersion,
} from '../../data/training.types';
import { problemsOf, settingsFrom } from '../../state/train-settings';
import { TrainingStore } from '../../state/training.store';
import { ExpertSettings } from '../expert-settings/expert-settings';
import { SimpleSettings } from '../simple-settings/simple-settings';
import { VersionRef } from '../version-ref/version-ref';

@Component({
  selector: 'app-train-form',
  imports: [
    BytesPipe,
    ExpertSettings,
    FormsModule,
    MatButton,
    MatCard,
    MatDivider,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSelectTrigger,
    MatSlideToggle,
    RouterLink,
    SimpleSettings,
    Term,
    TranslatePipe,
    VersionRef,
  ],
  templateUrl: './train-form.html',
  styleUrl: './train-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrainForm {
  private readonly store = inject(TrainingStore);
  private readonly ui = inject(UiModeStore);
  private readonly locale = inject(LocaleStore);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly limitMatchers = new Map<string, ErrorStateMatcher>();

  readonly projectId = this.store.projectId;
  readonly plan = this.store.plan;
  readonly planLoading = this.store.planLoading;
  readonly versions = this.store.versions;
  readonly datasets = this.store.datasets;
  readonly datasetsLoading = this.store.datasetsLoading;
  readonly starting = this.store.starting;
  readonly expert = this.ui.expert;
  readonly nameMax = NAME_MAX;

  readonly failure = signal<ApiError | null>(null);

  readonly defaults = computed<Hyperparams>(() => settingsFrom(this.plan()), {
    equal: (left, right) => JSON.stringify(left) === JSON.stringify(right),
  });
  readonly settings = linkedSignal<Hyperparams>(() => this.defaults());
  readonly startsFrom = linkedSignal<string | null>(
    () => (this.versions().find((version) => version.isActive) ?? this.versions()[0])?.id ?? null,
  );
  readonly chosen = linkedSignal<readonly LibraryDataset[], readonly DatasetChoice[]>({
    source: () => this.datasets(),
    computation: (library, previous) => (previous?.value ?? []).filter((choice) => library.some((dataset) => dataset.id === choice.id)),
  });
  readonly name = signal('');
  readonly useCorrections = signal(true);
  readonly activateWhenDone = signal(true);

  readonly corrections = computed(() => this.plan()?.corrections ?? 0);
  readonly fit = computed<Fit | null>(() => this.plan()?.fit ?? null);
  readonly fitIcon = computed(() => FIT_ICONS[this.fit()?.verdict ?? 'unknown']);
  readonly fitWarns = computed(() => this.fit()?.verdict === 'too_large');
  readonly fitTerm = computed(() => (this.fit()?.verdict === 'cpu_only' ? 'gpu' : 'vram'));

  readonly selected = computed<StartVersion | null>(
    () => this.versions().find((version) => version.id === this.startsFrom()) ?? null,
  );
  readonly startHint = computed(() => (this.selected()?.number === 0 ? 'training.form.startsFrom.base' : 'training.form.startsFrom.enhance'));

  readonly problems = computed(() => problemsOf(this.settings()));

  readonly chosenIds = computed(() => this.chosen().map((choice) => choice.id));
  readonly chosenRows = computed(() =>
    this.chosen().flatMap((choice) => {
      const dataset = this.datasets().find((item) => item.id === choice.id);
      return dataset === undefined ? [] : [{ choice, dataset }];
    }),
  );
  readonly limitsValid = computed(() => this.chosen().every((choice) => !this.limitInvalid(choice.maxRows)));

  readonly blocker = computed<string | null>(() => {
    if (this.plan() === null) {
      return null;
    }
    const replies = this.useCorrections() && this.corrections() > 0;
    if (!replies && this.chosen().length === 0) {
      return this.corrections() === 0 ? 'training.form.blocked.noReplies' : 'training.form.blocked.noSource';
    }
    return this.problems().length > 0 || !this.limitsValid() ? 'training.form.blocked.settings' : null;
  });

  readonly canStart = computed(() => this.plan() !== null && this.blocker() === null && !this.starting());

  async submit(): Promise<void> {
    if (!this.canStart()) {
      return;
    }
    this.failure.set(null);
    const draft: Draft = {
      startsFrom: this.startsFrom(),
      name: this.name(),
      useCorrections: this.useCorrections(),
      datasets: this.chosen(),
      activateWhenDone: this.activateWhenDone(),
      settings: this.settings(),
    };
    const result = await this.store.start(draft);
    if ('error' in result) {
      this.failure.set(result.error);
      if (result.error.code === 'dataset_not_ready') {
        this.store.reloadSetup();
      }
      return;
    }
    this.snackBar.open(this.locale.translate('training.form.started'), undefined, { duration: 4000 });
    await this.router.navigate(['/projects', this.projectId(), 'training', result.run.id]);
  }

  choose(ids: readonly string[]): void {
    this.chosen.update((current) => ids.map((id) => current.find((choice) => choice.id === id) ?? { id, maxRows: null }));
  }

  remove(id: string): void {
    this.chosen.update((current) => current.filter((choice) => choice.id !== id));
  }

  setLimit(id: string, value: number | null): void {
    this.chosen.update((current) => current.map((choice) => (choice.id === id ? { ...choice, maxRows: value } : choice)));
  }

  limitMatcher(id: string): ErrorStateMatcher {
    let matcher = this.limitMatchers.get(id);
    if (matcher === undefined) {
      matcher = { isErrorState: () => this.limitInvalid(this.chosen().find((choice) => choice.id === id)?.maxRows ?? null) };
      this.limitMatchers.set(id, matcher);
    }
    return matcher;
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  private limitInvalid(value: number | null): boolean {
    return value !== null && (!Number.isInteger(value) || value < 1);
  }
}
