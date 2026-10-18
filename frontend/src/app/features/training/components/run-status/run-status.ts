import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { MatIcon } from '@angular/material/icon';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber } from '@shared/format/format';
import { FINISHED_STATUSES, STATUS_LOOKS, type Run, type StatusLook } from '../../data/training.types';

const PREPARING_STAGES: readonly string[] = ['data', 'tokenizer', 'model', 'parent'];

@Component({
  selector: 'app-run-status',
  imports: [MatIcon, TranslatePipe],
  templateUrl: './run-status.html',
  styleUrl: './run-status.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunStatus {
  private readonly locale = inject(LocaleStore);

  readonly run = input.required<Run>();
  readonly stopping = input(false);

  readonly look = computed<StatusLook>(() => STATUS_LOOKS[this.run().status]);

  readonly key = computed(() => {
    const run = this.run();
    if (FINISHED_STATUSES.includes(run.status)) {
      return `training.status.${run.status}`;
    }
    if (this.stopping()) {
      return 'training.stage.stopping';
    }
    if (run.stage === 'oom_retry') {
      return 'training.stage.oom_retry';
    }
    switch (run.status) {
      case 'queued':
        return 'training.stage.queued';
      case 'preparing':
        return PREPARING_STAGES.includes(run.stage) ? `training.stage.${run.stage}` : 'training.stage.data';
      case 'training':
        return run.total_steps > 0 ? 'training.stage.training' : 'training.stage.begin';
      default:
        return 'training.stage.saving';
    }
  });

  readonly values = computed(() => {
    const run = this.run();
    const locale = this.locale.locale();
    return {
      step: formatNumber(run.step, locale),
      total: formatNumber(run.total_steps, locale),
      version: run.starts_from === null ? '' : `v${run.starts_from.number}`,
    };
  });
}
