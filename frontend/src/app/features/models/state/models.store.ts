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
  startWith,
  switchMap,
  type Observable,
} from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { ModelsApi } from '../data/models.api';
import {
  ACTIVE_STATUSES,
  POPULAR,
  type HubQuery,
  type HubResult,
  type Inspection,
  type LibraryModel,
} from '../data/models.types';

const PAGE_SIZE = 25;
const POLL_MS = 2000;

@Injectable()
export class ModelsStore {
  private readonly api = inject(ModelsApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);
  private readonly loaded = new Subject<void>();

  readonly page = signal<Page<LibraryModel>>(EMPTY_PAGE);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(PAGE_SIZE);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly working = signal<readonly string[]>([]);
  readonly adding = signal(false);

  readonly hubQuery = signal<HubQuery>(POPULAR);

  private readonly inspectedRepo = signal<string | null>(null);

  private readonly hub = rxResource({
    params: () => this.hubQuery(),
    stream: ({ params }) => this.api.hub(params),
  });

  private readonly inspected = rxResource({
    params: () => this.inspectedRepo() ?? undefined,
    stream: ({ params }) => this.api.inspect(params),
  });

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  readonly downloading = computed(() => this.page().results.some((model) => ACTIVE_STATUSES.includes(model.status)));

  readonly hubResults = computed<readonly HubResult[]>(() => (this.hub.hasValue() ? this.hub.value().results : []));
  readonly hubLoading = computed(() => this.hub.isLoading());
  readonly hubError = computed(() => this.failure(this.hub.status() === 'error' ? this.hub.error() : undefined));

  readonly inspection = computed<Inspection | null>(() => (this.inspected.hasValue() ? this.inspected.value() : null));
  readonly inspecting = computed(() => this.inspected.isLoading());
  readonly inspectionError = computed(() =>
    this.failure(this.inspected.status() === 'error' ? this.inspected.error() : undefined),
  );

  async load(pageIndex = this.pageIndex(), pageSize = this.pageSize()): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      await this.fetch(pageIndex, pageSize);
    } catch (error) {
      this.error.set(error as ApiError);
    } finally {
      this.loading.set(false);
    }
  }

  private async refresh(): Promise<void> {
    try {
      await this.fetch(this.pageIndex(), this.pageSize());
    } catch {
      // A failed background refresh keeps the last list on screen; the next one tries again.
    }
  }

  watchDownloads(): Observable<void> {
    return this.loaded.pipe(
      startWith(undefined),
      map(() => this.downloading()),
      distinctUntilChanged(),
      switchMap((active) => (active ? interval(POLL_MS) : EMPTY)),
      exhaustMap(() => this.refresh()),
    );
  }

  search(query: HubQuery): void {
    this.hubQuery.set({ ...query, search: query.search.trim() });
  }

  searchAgain(): void {
    this.hub.reload();
  }

  inspect(repo: string): void {
    this.inspectedRepo.set(repo);
  }

  inspectAgain(): void {
    this.inspected.reload();
  }

  stopInspecting(): void {
    this.inspectedRepo.set(null);
  }

  async add(repo: string): Promise<ApiError | null> {
    this.adding.set(true);
    try {
      await firstValueFrom(this.api.add({ repo_id: repo }));
      await this.load(0);
      this.hub.reload();
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.adding.set(false);
    }
  }

  cancel(model: LibraryModel): Promise<boolean> {
    return this.mutate(model.id, async () => {
      this.replace(await firstValueFrom(this.api.cancel(model.id)));
    });
  }

  retry(model: LibraryModel): Promise<boolean> {
    return this.mutate(model.id, async () => {
      this.replace(await firstValueFrom(this.api.retry(model.id)));
    });
  }

  remove(model: LibraryModel): Promise<boolean> {
    return this.mutate(model.id, async () => {
      await firstValueFrom(this.api.remove(model.id));
      await this.fetch(this.indexAfterRemoval(), this.pageSize());
      this.hub.reload();
    });
  }

  private async fetch(pageIndex: number, pageSize: number): Promise<void> {
    this.page.set(await firstValueFrom(this.api.library({ page: pageIndex + 1, page_size: pageSize })));
    this.pageIndex.set(pageIndex);
    this.pageSize.set(pageSize);
    this.loaded.next();
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

  private replace(updated: LibraryModel): void {
    this.page.update((page) => ({
      ...page,
      results: page.results.map((row) => (row.id === updated.id ? updated : row)),
    }));
    this.loaded.next();
  }

  private indexAfterRemoval(): number {
    const remaining = this.page().count - 1;
    const lastIndex = Math.max(0, Math.ceil(remaining / this.pageSize()) - 1);
    return Math.min(this.pageIndex(), lastIndex);
  }

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
