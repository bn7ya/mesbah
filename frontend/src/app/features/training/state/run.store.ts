import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import {
  EMPTY,
  Subject,
  distinctUntilChanged,
  exhaustMap,
  firstValueFrom,
  interval,
  map,
  merge,
  startWith,
  switchMap,
  tap,
  ignoreElements,
  type Observable,
} from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError, Page } from '@core/http/api.types';
import { TrainingApi } from '../data/training.api';
import {
  CLOCK_MS,
  FINISHED_STATUSES,
  PACE_SAMPLES,
  RUN_POLL_MS,
  STOPPABLE_STATUSES,
  type LossReading,
  type Metric,
  type Run,
  type StepSample,
  type VersionSize,
} from '../data/training.types';
import { readLoss } from './loss-trend';
import { secondsLeft } from './pace';

@Injectable()
export class RunStore {
  private readonly api = inject(TrainingApi);
  private readonly auth = inject(AuthStore);
  private readonly loaded = new Subject<void>();
  private pulling: { readonly id: string; readonly promise: Promise<void> } | null = null;

  readonly runId = signal<string | null>(null);
  readonly run = signal<Run | null>(null);
  readonly points = signal<readonly Metric[]>([]);
  readonly samples = signal<readonly StepSample[]>([]);
  readonly now = signal(Date.now());
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  private readonly stopAsked = signal(false);
  readonly stopError = signal<ApiError | null>(null);

  private readonly sized = rxResource({
    params: () => {
      const run = this.run();
      return run?.status === 'completed' && run.version !== null ? run.version.id : undefined;
    },
    stream: ({ params }) => this.api.versionSize(params),
  });

  readonly size = computed<VersionSize | null>(() => (this.sized.hasValue() ? this.sized.value() : null));

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));
  readonly finished = computed(() => {
    const run = this.run();
    return run !== null && FINISHED_STATUSES.includes(run.status);
  });
  readonly stopping = computed(() => !this.finished() && (this.stopAsked() || this.run()?.cancel_requested === true));
  readonly canStop = computed(() => {
    const run = this.run();
    return this.canWrite() && run !== null && STOPPABLE_STATUSES.includes(run.status);
  });
  readonly reading = computed<LossReading>(() => readLoss(this.points()));

  readonly progress = computed(() => {
    const run = this.run();
    if (run === null) {
      return 0;
    }
    if (run.status === 'completed') {
      return 100;
    }
    return run.total_steps > 0 ? Math.min(100, Math.round((run.step / run.total_steps) * 100)) : 0;
  });

  readonly elapsedSeconds = computed<number | null>(() => {
    const run = this.run();
    if (run === null || run.started_at === null) {
      return null;
    }
    const end = run.finished_at === null ? this.now() : Date.parse(run.finished_at);
    return Math.max(0, (end - Date.parse(run.started_at)) / 1000);
  });

  readonly remainingSeconds = computed<number | null>(() => {
    const run = this.run();
    return run?.status === 'training' ? secondsLeft(this.samples(), run.total_steps) : null;
  });

  open(id: string): void {
    if (this.runId() !== id) {
      this.runId.set(id);
      this.run.set(null);
      this.points.set([]);
      this.samples.set([]);
      this.stopAsked.set(false);
    }
    this.stopError.set(null);
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      await this.pull();
    } catch (error) {
      this.error.set(error as ApiError);
    } finally {
      this.loading.set(false);
    }
  }

  watch(): Observable<void> {
    return this.loaded.pipe(
      startWith(undefined),
      map(() => this.run() !== null && !this.finished()),
      distinctUntilChanged(),
      switchMap((active) =>
        active
          ? merge(
              interval(RUN_POLL_MS).pipe(exhaustMap(() => this.refresh())),
              interval(CLOCK_MS).pipe(
                tap(() => this.now.set(Date.now())),
                ignoreElements(),
              ),
            )
          : EMPTY,
      ),
    );
  }

  async stop(): Promise<boolean> {
    const id = this.runId();
    if (id === null) {
      return false;
    }
    this.stopError.set(null);
    this.stopAsked.set(true);
    try {
      this.run.set(await firstValueFrom(this.api.cancel(id)));
      this.loaded.next();
      return true;
    } catch (error) {
      this.stopError.set(error as ApiError);
      this.stopAsked.set(false);
      return false;
    }
  }

  private async refresh(): Promise<void> {
    try {
      await this.pull();
    } catch {
      // A failed background poll keeps what is on screen; the next one tries again.
    }
  }

  private pull(): Promise<void> {
    const id = this.runId();
    if (id === null) {
      return Promise.resolve();
    }
    if (this.pulling?.id === id) {
      return this.pulling.promise;
    }
    const pulling = {
      id,
      promise: this.fetch(id).finally(() => {
        if (this.pulling === pulling) {
          this.pulling = null;
        }
      }),
    };
    this.pulling = pulling;
    return pulling.promise;
  }

  private async fetch(id: string): Promise<void> {
    const run = await firstValueFrom(this.api.run(id));
    if (this.runId() !== id) {
      return;
    }
    this.now.set(Date.now());
    this.run.set(run);
    this.sample(run);
    await this.appendPoints(id);
    if (FINISHED_STATUSES.includes(run.status)) {
      this.stopAsked.set(false);
    }
    this.loaded.next();
  }

  private sample(run: Run): void {
    if (run.status === 'training') {
      const next: StepSample = { at: Date.now(), step: run.step };
      this.samples.update((samples) => [...samples, next].slice(-PACE_SAMPLES));
    }
  }

  private async appendPoints(id: string): Promise<void> {
    let next: number | null = 1;
    const after = this.points().at(-1)?.step ?? 0;
    const fresh: Metric[] = [];
    while (next !== null) {
      const page: Page<Metric> = await firstValueFrom(this.api.metrics(id, after, next));
      fresh.push(...page.results);
      next = page.next === null ? null : next + 1;
    }
    if (this.runId() === id && fresh.length > 0) {
      this.points.update((points) => [...points, ...fresh.filter((point) => point.step > (points.at(-1)?.step ?? 0))]);
    }
  }
}
