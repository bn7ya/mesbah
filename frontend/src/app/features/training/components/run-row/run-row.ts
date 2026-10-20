import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { formatNumber, formatSignificant } from '@shared/format/format';
import { FINISHED_STATUSES, STOPPABLE_STATUSES, type Run, type RunSource } from '../../data/training.types';
import { sourcesOf } from '../../state/run-sources';
import { TrainingStore } from '../../state/training.store';
import { RunStatus } from '../run-status/run-status';
import { VersionRef } from '../version-ref/version-ref';

@Component({
  selector: 'app-run-row',
  imports: [DateTimePipe, MatButton, MatCard, MatIcon, MatProgressBar, RouterLink, RunStatus, TranslatePipe, VersionRef],
  templateUrl: './run-row.html',
  styleUrl: './run-row.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunRow {
  private readonly store = inject(TrainingStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly run = input.required<Run>();

  readonly projectId = this.store.projectId;
  readonly canWrite = this.store.canWrite;

  readonly pretrain = computed(() => this.run().kind === 'pretrain');
  readonly title = computed(() => {
    const run = this.run();
    return run.kind === 'pretrain'
      ? this.locale.translate('training.runs.pretrainName')
      : run.name || this.locale.translate('training.runs.unnamed');
  });
  readonly sources = computed<readonly RunSource[] | null>(() => sourcesOf(this.run().corrections_from, this.store.sourceNames()));
  readonly sourceCount = computed(() => formatNumber(this.run().corrections_from.length, this.locale.locale()));

  readonly finished = computed(() => FINISHED_STATUSES.includes(this.run().status));
  readonly busy = computed(() => this.store.working().includes(this.run().id));
  readonly stopRequested = computed(
    () => !this.finished() && (this.run().cancel_requested || this.store.stopping().includes(this.run().id)),
  );
  readonly canStop = computed(() => this.canWrite() && STOPPABLE_STATUSES.includes(this.run().status) && !this.stopRequested());
  readonly canRemove = computed(() => this.canWrite() && this.finished());

  readonly steps = computed(() => {
    const run = this.run();
    return run.status === 'training' && run.total_steps > 0;
  });
  readonly percent = computed(() => {
    const run = this.run();
    return run.total_steps > 0 ? Math.min(100, (run.step / run.total_steps) * 100) : 0;
  });
  readonly indeterminate = computed(() => !this.finished() && !this.steps());
  readonly showBar = computed(() => this.steps() || this.indeterminate() || this.run().status === 'completed');
  readonly barValue = computed(() => (this.run().status === 'completed' ? 100 : this.percent()));

  readonly loss = computed(() => {
    const loss = this.run().loss;
    return loss === null ? null : formatSignificant(loss, this.locale.locale(), 3);
  });

  async stop(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'training.runs.stop.title',
      bodyKey: 'training.runs.stop.body',
      confirmKey: 'training.runs.stop.confirm',
      destructive: true,
    });
    if (confirmed && (await this.store.stop(this.run()))) {
      this.report('training.runs.stopped');
    }
  }

  async remove(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'training.runs.remove.title',
      bodyKey: 'training.runs.remove.body',
      confirmKey: 'training.runs.remove.confirm',
      destructive: true,
    });
    if (confirmed && (await this.store.remove(this.run()))) {
      this.report('training.runs.removed');
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
