import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import {
  EMPTY,
  Subject,
  distinctUntilChanged,
  exhaustMap,
  expand,
  firstValueFrom,
  interval,
  map,
  reduce,
  startWith,
  switchMap,
  type Observable,
} from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TrainingApi } from '../data/training.api';
import {
  DEFAULT_PAGE_SIZE,
  FINISHED_STATUSES,
  RUNS_POLL_MS,
  type Draft,
  type Example,
  type LibraryDataset,
  type Plan,
  type Run,
  type SourceNames,
  type StartResult,
  type StartVersion,
} from '../data/training.types';

@Injectable()
export class TrainingStore {
  private readonly api = inject(TrainingApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);
  private readonly loaded = new Subject<void>();

  readonly projectId = signal<string | null>(null);

  readonly runs = signal<Page<Run>>(EMPTY_PAGE);
  readonly runsPageIndex = signal(0);
  readonly runsPageSize = signal(DEFAULT_PAGE_SIZE);
  readonly runsLoading = signal(false);
  readonly runsError = signal<ApiError | null>(null);

  readonly examples = signal<Page<Example>>(EMPTY_PAGE);
  readonly examplesPageIndex = signal(0);
  readonly examplesPageSize = signal(DEFAULT_PAGE_SIZE);
  readonly examplesLoading = signal(false);
  readonly examplesError = signal<ApiError | null>(null);

  readonly starting = signal(false);
  readonly working = signal<readonly string[]>([]);
  readonly stopping = signal<readonly string[]>([]);
  readonly error = signal<ApiError | null>(null);

  private readonly planned = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => this.api.plan(params),
  });

  private readonly versionList = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => this.collectVersions(params),
  });

  private readonly datasetList = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: () => this.collectDatasets(),
  });

  private readonly sourceKey = computed(() => {
    const ids = this.runs().results.flatMap((run) => (run.kind === 'pretrain' ? run.corrections_from : []));
    return [...new Set(ids)].sort().join(',');
  });

  private readonly sourceList = rxResource({
    params: () => this.sourceKey() || undefined,
    stream: ({ params }) => this.api.projectNames(params.split(',')),
  });

  readonly plan = computed<Plan | null>(() => (this.planned.hasValue() ? this.planned.value() : null));
  readonly planLoading = computed(() => this.planned.isLoading());
  readonly planError = computed(() => this.failure(this.planned.status() === 'error' ? this.planned.error() : undefined));

  readonly versions = computed<readonly StartVersion[]>(() => (this.versionList.hasValue() ? this.versionList.value() : []));
  readonly versionsLoading = computed(() => this.versionList.isLoading());
  readonly versionsError = computed(() =>
    this.failure(this.versionList.status() === 'error' ? this.versionList.error() : undefined),
  );

  readonly datasets = computed<readonly LibraryDataset[]>(() => (this.datasetList.hasValue() ? this.datasetList.value() : []));
  readonly datasetsLoading = computed(() => this.datasetList.isLoading());
  readonly datasetsError = computed(() =>
    this.failure(this.datasetList.status() === 'error' ? this.datasetList.error() : undefined),
  );

  readonly sourceNames = computed<SourceNames | null>(() => (this.sourceList.hasValue() ? this.sourceList.value() : null));
  readonly noModel = computed(() => this.versionList.hasValue() && this.versionList.value().length === 0);

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));
  readonly unfinished = computed(() => this.runs().results.some((run) => !FINISHED_STATUSES.includes(run.status)));

  open(projectId: string): void {
    if (this.projectId() === projectId) {
      this.reloadSetup();
    } else {
      this.projectId.set(projectId);
      this.runs.set(EMPTY_PAGE);
      this.runsPageIndex.set(0);
      this.examples.set(EMPTY_PAGE);
      this.examplesPageIndex.set(0);
    }
    this.error.set(null);
    void this.loadRuns(this.runsPageIndex());
  }

  reloadSetup(): void {
    this.planned.reload();
    this.versionList.reload();
    this.datasetList.reload();
  }

  async loadRuns(pageIndex = this.runsPageIndex(), pageSize = this.runsPageSize()): Promise<void> {
    this.runsLoading.set(true);
    this.runsError.set(null);
    try {
      await this.fetchRuns(pageIndex, pageSize);
    } catch (error) {
      this.runsError.set(error as ApiError);
    } finally {
      this.runsLoading.set(false);
    }
  }

  async loadExamples(pageIndex = this.examplesPageIndex(), pageSize = this.examplesPageSize()): Promise<void> {
    const project = this.projectId();
    if (project === null) {
      return;
    }
    this.examplesLoading.set(true);
    this.examplesError.set(null);
    try {
      const page = await firstValueFrom(this.api.examples(project, pageIndex + 1, pageSize));
      this.examples.set(page);
      this.examplesPageIndex.set(pageIndex);
      this.examplesPageSize.set(pageSize);
    } catch (error) {
      this.examplesError.set(error as ApiError);
    } finally {
      this.examplesLoading.set(false);
    }
  }

  watchRuns(): Observable<void> {
    return this.loaded.pipe(
      startWith(undefined),
      map(() => this.unfinished()),
      distinctUntilChanged(),
      switchMap((active) => (active ? interval(RUNS_POLL_MS) : EMPTY)),
      exhaustMap(() => this.refreshRuns()),
    );
  }

  async start(draft: Draft): Promise<StartResult> {
    const project = this.projectId();
    if (project === null) {
      return { error: { code: 'unknown', message: this.locale.translate('errors.generic') } };
    }
    this.starting.set(true);
    try {
      return { run: await firstValueFrom(this.api.start(project, draft)) };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.starting.set(false);
    }
  }

  stop(run: Run): Promise<boolean> {
    return this.mutate(run.id, async () => {
      const updated = await firstValueFrom(this.api.cancel(run.id));
      if (!FINISHED_STATUSES.includes(updated.status)) {
        this.stopping.update((ids) => [...ids, updated.id]);
      }
      this.runs.update((page) => ({
        ...page,
        results: page.results.map((row) => (row.id === updated.id ? updated : row)),
      }));
      this.loaded.next();
    });
  }

  remove(run: Run): Promise<boolean> {
    return this.mutate(run.id, async () => {
      await firstValueFrom(this.api.remove(run.id));
      const last = this.runs().results.length === 1 && this.runsPageIndex() > 0;
      await this.fetchRuns(last ? this.runsPageIndex() - 1 : this.runsPageIndex(), this.runsPageSize());
    });
  }

  private async fetchRuns(pageIndex: number, pageSize: number): Promise<void> {
    const project = this.projectId();
    if (project === null) {
      return;
    }
    const page = await firstValueFrom(this.api.runs(project, pageIndex + 1, pageSize));
    this.runs.set(page);
    this.runsPageIndex.set(pageIndex);
    this.runsPageSize.set(pageSize);
    this.loaded.next();
  }

  private async refreshRuns(): Promise<void> {
    const wasUnfinished = this.unfinished();
    try {
      await this.fetchRuns(this.runsPageIndex(), this.runsPageSize());
    } catch {
      // A failed background refresh keeps the last list on screen; the next one tries again.
      return;
    }
    if (wasUnfinished && !this.unfinished()) {
      this.reloadSetup();
    }
  }

  private collectDatasets(): Observable<readonly LibraryDataset[]> {
    return this.api.datasets(1).pipe(
      expand((page, index) => (page.next === null ? EMPTY : this.api.datasets(index + 2))),
      reduce((all: readonly LibraryDataset[], page: Page<LibraryDataset>) => [...all, ...page.results], [] as readonly LibraryDataset[]),
    );
  }

  private collectVersions(project: string): Observable<readonly StartVersion[]> {
    return this.api.versions(project, 1).pipe(
      expand((page, index) => (page.next === null ? EMPTY : this.api.versions(project, index + 2))),
      reduce((all: readonly StartVersion[], page: Page<StartVersion>) => [...all, ...page.results], [] as readonly StartVersion[]),
    );
  }

  private async mutate(id: string, action: () => Promise<void>): Promise<boolean> {
    this.working.update((ids) => [...ids, id]);
    this.error.set(null);
    try {
      await action();
      return true;
    } catch (error) {
      this.error.set(error as ApiError);
      return false;
    } finally {
      this.working.update((ids) => ids.filter((working) => working !== id));
    }
  }

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
