import { ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionPanel, MatExpansionPanelHeader, MatExpansionPanelTitle } from '@angular/material/expansion';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { CodeBlock } from '@shared/code-block/code-block';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { formatNumber, formatPercent, formatSignificant } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Status } from '@shared/status/status';
import { Term } from '@shared/term/term';
import { RunChart } from '../../components/run-chart/run-chart';
import { RunStatus } from '../../components/run-status/run-status';
import { VersionRef } from '../../components/version-ref/version-ref';
import {
  FAILURE_CODES,
  PRETRAIN_FAILURE_CODES,
  SETTING_LABELS,
  SLIVER,
  TREND_ICONS,
  type ChartData,
  type RunSource,
  type SettingRow,
  type SizeShare,
} from '../../data/training.types';
import { formatDuration } from '../../state/pace';
import { RunStore } from '../../state/run.store';
import { sourcesOf } from '../../state/run-sources';
import { settingValue, shownSettings } from '../../state/run-settings';

@Component({
  selector: 'app-run-page',
  imports: [
    BytesPipe,
    CodeBlock,
    CompactPipe,
    DateTimePipe,
    MatButton,
    MatCard,
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
    MatIcon,
    MatProgressBar,
    Note,
    RouterLink,
    RunChart,
    RunStatus,
    Status,
    Term,
    TranslatePipe,
    VersionRef,
  ],
  templateUrl: './run.html',
  styleUrl: './run.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunPage {
  private readonly store = inject(RunStore);
  private readonly ui = inject(UiModeStore);
  private readonly locale = inject(LocaleStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly projectId = input.required<string>();
  readonly runId = input.required<string>();

  readonly run = this.store.run;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly finished = this.store.finished;
  readonly canStop = this.store.canStop;
  readonly stopping = this.store.stopping;
  readonly stopError = this.store.stopError;
  readonly progress = this.store.progress;
  readonly expert = this.ui.expert;

  readonly pretrain = computed(() => this.run()?.kind === 'pretrain');
  readonly title = computed(() => {
    const run = this.run();
    if (run?.kind === 'pretrain') {
      return this.locale.translate('training.runs.pretrainName');
    }
    return run?.name || this.locale.translate('training.run.untitled');
  });

  readonly showBar = computed(() => {
    const run = this.run();
    return run !== null && (!this.finished() || run.status === 'completed');
  });
  readonly steady = computed(() => {
    const run = this.run();
    return run !== null && (run.status === 'completed' || (run.status === 'training' && run.total_steps > 0));
  });

  readonly elapsed = computed(() => {
    const seconds = this.store.elapsedSeconds();
    return seconds === null ? null : formatDuration(seconds, this.locale.locale());
  });
  readonly remaining = computed(() => {
    const seconds = this.store.remainingSeconds();
    return seconds === null ? null : formatDuration(seconds, this.locale.locale());
  });
  readonly estimating = computed(() => this.run()?.status === 'training' && this.remaining() === null);

  readonly percent = computed(() => formatPercent(this.progress() / 100, this.locale.locale()));

  readonly reading = this.store.reading;
  readonly trendIcon = computed(() => TREND_ICONS[this.reading().trend]);
  readonly lossSentence = computed(() => {
    const { trend, first, latest } = this.reading();
    const locale = this.locale.locale();
    const show = (value: number | null): string => (value === null ? '' : formatSignificant(value, locale, 3));
    return {
      key: `training.loss.${this.finished() ? 'done' : 'live'}.${trend}`,
      values: { first: show(first), latest: show(latest) },
    };
  });

  readonly lossChart = computed<ChartData | null>(() => {
    const points = this.store.points().filter((point) => point.loss !== null);
    if (points.length === 0) {
      return null;
    }
    const label = this.locale.translate('training.chart.loss');
    return {
      steps: points.map((point) => point.step),
      series: [{ id: 'loss', label, values: points.map((point) => point.loss), color: 'primary', axis: 'left', axisTitle: label }],
      stepTitle: this.locale.translate('training.chart.step'),
      summary: this.locale.translate(this.lossSentence().key, this.lossSentence().values),
    };
  });

  readonly paceChart = computed<ChartData | null>(() => {
    const points = this.store.points().filter((point) => point.learning_rate !== null || point.grad_norm !== null);
    if (points.length === 0) {
      return null;
    }
    const rate = this.locale.translate('training.chart.rate');
    const norm = this.locale.translate('training.chart.norm');
    return {
      steps: points.map((point) => point.step),
      series: [
        { id: 'rate', label: rate, values: points.map((point) => point.learning_rate), color: 'primary', axis: 'left', axisTitle: rate },
        { id: 'norm', label: norm, values: points.map((point) => point.grad_norm), color: 'tertiary', axis: 'right', axisTitle: norm },
      ],
      stepTitle: this.locale.translate('training.chart.step'),
      summary: this.locale.translate('training.chart.paceSummary'),
    };
  });

  readonly failureKey = computed(() => {
    const run = this.run();
    const code = run?.error_code ?? '';
    if (run?.kind === 'pretrain' && PRETRAIN_FAILURE_CODES.includes(code)) {
      return `training.failure.pretrain.${code}`;
    }
    return `training.failure.${FAILURE_CODES.includes(code) ? code : 'failed'}`;
  });
  readonly missingParts = computed(() => this.run()?.error_code === 'training_parts_missing');

  readonly share = computed<SizeShare | null>(() => {
    const size = this.store.size();
    if (size === null || size.fullSizeBytes <= 0) {
      return null;
    }
    const ratio = Math.min(1, size.sizeBytes / size.fullSizeBytes);
    const sliver = ratio < SLIVER;
    return {
      ratio,
      bytes: size.sizeBytes,
      key: sliver ? 'training.result.sliver' : 'training.result.size',
      percent: formatPercent(sliver ? SLIVER : ratio, this.locale.locale()),
    };
  });
  readonly finalLoss = computed(() => {
    const loss = this.run()?.loss;
    return loss === null || loss === undefined ? null : formatSignificant(loss, this.locale.locale(), 3);
  });

  readonly sources = computed<readonly RunSource[] | null>(() => sourcesOf(this.run()?.corrections_from ?? [], this.store.sourceNames()));

  readonly settings = computed<readonly SettingRow[]>(() => {
    const used = this.run()?.hyperparams ?? {};
    return shownSettings(used, this.expert()).map((key) => {
      const value = settingValue(used, key);
      return {
        key,
        labelKey: SETTING_LABELS[key],
        text: this.settingText(value),
        termKey: key === 'optim' && typeof value === 'string' ? value : null,
      };
    });
  });

  readonly processor = computed(() => (this.run()?.gpu_indices.length ?? 0) === 0);
  readonly epoch = computed(() => {
    const epoch = this.run()?.epoch;
    return epoch === null || epoch === undefined ? null : formatNumber(epoch, this.locale.locale(), 2);
  });

  constructor() {
    effect(() => {
      const id = this.runId();
      untracked(() => this.store.open(id));
    });
    this.store.watch().pipe(takeUntilDestroyed()).subscribe();
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  tryAgain(): void {
    void this.store.load();
  }

  async stop(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'training.runs.stop.title',
      bodyKey: 'training.runs.stop.body',
      confirmKey: 'training.runs.stop.confirm',
      destructive: true,
    });
    if (confirmed && (await this.store.stop())) {
      this.snackBar.open(this.locale.translate('training.runs.stopped'), undefined, { duration: 4000 });
    }
  }

  private settingText(value: number | boolean | string | null | undefined): string {
    if (typeof value === 'string') {
      return value;
    }
    if (typeof value === 'boolean') {
      return this.locale.translate(value ? 'training.run.yes' : 'training.run.no');
    }
    if (value === null || value === undefined) {
      return this.locale.translate('training.expert.none');
    }
    return formatSignificant(value, this.locale.locale(), 6);
  }
}
