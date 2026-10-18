import { HttpEventType, type HttpEvent } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import {
  EMPTY,
  Subject,
  distinctUntilChanged,
  exhaustMap,
  firstValueFrom,
  interval,
  lastValueFrom,
  map,
  startWith,
  switchMap,
  tap,
  type Observable,
} from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { DatasetsApi } from '../data/datasets.api';
import {
  ACTIVE_STATUSES,
  type Conversation,
  type Dataset,
  type DatasetChanges,
  type HubDataset,
  type InspectQuery,
  type Inspection,
  type NewImport,
} from '../data/datasets.types';

const PAGE_SIZE = 25;
const ROWS_PAGE_SIZE = 10;
const POLL_MS = 2000;

@Injectable()
export class DatasetsStore {
  private readonly api = inject(DatasetsApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);
  private readonly loaded = new Subject<void>();
  private readonly openedChanged = new Subject<void>();

  readonly page = signal<Page<Dataset>>(EMPTY_PAGE);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(PAGE_SIZE);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly working = signal<readonly string[]>([]);
  readonly importing = signal(false);
  readonly uploadProgress = signal<number | null>(null);

  readonly opened = signal<Dataset | null>(null);
  readonly openError = signal<ApiError | null>(null);
  readonly rows = signal<Page<Conversation>>(EMPTY_PAGE);
  readonly rowsIndex = signal(0);
  readonly rowsSize = signal(ROWS_PAGE_SIZE);
  readonly rowsLoading = signal(false);
  readonly rowsError = signal<ApiError | null>(null);

  readonly hubQuery = signal('');

  private readonly inspectQuery = signal<InspectQuery | null>(null);

  private readonly hub = rxResource({
    params: () => ({ search: this.hubQuery() }),
    stream: ({ params }) => this.api.hub(params.search),
  });

  private readonly inspected = rxResource({
    params: () => this.inspectQuery() ?? undefined,
    stream: ({ params }) => this.api.inspect(params),
  });

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  readonly busy = computed(() => this.page().results.some((dataset) => ACTIVE_STATUSES.includes(dataset.status)));
  readonly uploading = computed(() => this.uploadProgress() !== null);
  readonly openedBusy = computed(() => {
    const dataset = this.opened();
    return dataset !== null && ACTIVE_STATUSES.includes(dataset.status);
  });

  readonly hubResults = computed<readonly HubDataset[]>(() => (this.hub.hasValue() ? this.hub.value().results : []));
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

  watchImports(): Observable<void> {
    return this.polling(this.loaded, () => this.busy(), () => this.refresh());
  }

  search(words: string): void {
    this.hubQuery.set(words.trim());
  }

  searchAgain(): void {
    this.hub.reload();
  }

  inspect(query: InspectQuery): void {
    this.inspectQuery.set(query);
  }

  inspectAgain(): void {
    this.inspected.reload();
  }

  stopInspecting(): void {
    this.inspectQuery.set(null);
  }

  async startImport(request: NewImport): Promise<ApiError | null> {
    this.importing.set(true);
    try {
      await firstValueFrom(this.api.import(request));
      await this.load(0);
      this.hub.reload();
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.importing.set(false);
    }
  }

  async upload(file: File, name = ''): Promise<ApiError | null> {
    this.uploadProgress.set(0);
    try {
      await lastValueFrom(this.api.upload(file, name).pipe(tap((event) => this.track(event))));
      await this.load(0);
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.uploadProgress.set(null);
    }
  }

  cancel(dataset: Dataset): Promise<boolean> {
    return this.mutate(dataset.id, async () => {
      this.replace(await firstValueFrom(this.api.cancel(dataset.id)));
    });
  }

  retry(dataset: Dataset): Promise<boolean> {
    return this.mutate(dataset.id, async () => {
      this.replace(await firstValueFrom(this.api.retry(dataset.id)));
    });
  }

  remove(dataset: Dataset): Promise<boolean> {
    return this.mutate(dataset.id, async () => {
      await firstValueFrom(this.api.remove(dataset.id));
      if (this.opened()?.id === dataset.id) {
        this.opened.set(null);
      }
      await this.fetch(this.indexAfterRemoval(), this.pageSize());
      this.hub.reload();
    });
  }

  async update(dataset: Dataset, changes: DatasetChanges): Promise<ApiError | null> {
    try {
      this.replace(await firstValueFrom(this.api.update(dataset.id, changes)));
      return null;
    } catch (error) {
      return error as ApiError;
    }
  }

  async open(id: string): Promise<void> {
    this.openError.set(null);
    this.rows.set(EMPTY_PAGE);
    this.rowsIndex.set(0);
    try {
      this.setOpened(await firstValueFrom(this.api.find(id)));
    } catch (error) {
      this.opened.set(null);
      this.openError.set(error as ApiError);
      return;
    }
    if (this.opened()?.status === 'ready') {
      await this.loadRows(0);
    }
  }

  watchOpened(): Observable<void> {
    return this.polling(this.openedChanged, () => this.openedBusy(), () => this.refreshOpened());
  }

  async loadRows(pageIndex = this.rowsIndex(), pageSize = this.rowsSize()): Promise<void> {
    const dataset = this.opened();
    if (dataset === null) {
      return;
    }
    this.rowsLoading.set(true);
    this.rowsError.set(null);
    try {
      this.rows.set(await firstValueFrom(this.api.rows(dataset.id, { page: pageIndex + 1, page_size: pageSize })));
      this.rowsIndex.set(pageIndex);
      this.rowsSize.set(pageSize);
    } catch (error) {
      this.rowsError.set(error as ApiError);
    } finally {
      this.rowsLoading.set(false);
    }
  }

  private polling(changes: Subject<void>, active: () => boolean, tick: () => Promise<void>): Observable<void> {
    return changes.pipe(
      startWith(undefined),
      map(active),
      distinctUntilChanged(),
      switchMap((running) => (running ? interval(POLL_MS) : EMPTY)),
      exhaustMap(tick),
    );
  }

  private async refresh(): Promise<void> {
    try {
      await this.fetch(this.pageIndex(), this.pageSize());
    } catch {
      // A failed background refresh keeps the last list on screen; the next one tries again.
    }
  }

  private async refreshOpened(): Promise<void> {
    const dataset = this.opened();
    if (dataset === null) {
      return;
    }
    try {
      this.setOpened(await firstValueFrom(this.api.find(dataset.id)));
    } catch {
      return;
    }
    if (this.opened()?.status === 'ready') {
      await this.loadRows(0);
    }
  }

  private async fetch(pageIndex: number, pageSize: number): Promise<void> {
    this.page.set(await firstValueFrom(this.api.library({ page: pageIndex + 1, page_size: pageSize })));
    this.pageIndex.set(pageIndex);
    this.pageSize.set(pageSize);
    this.loaded.next();
  }

  private track(event: HttpEvent<Dataset>): void {
    if (event.type === HttpEventType.UploadProgress && event.total) {
      this.uploadProgress.set(Math.round((event.loaded / event.total) * 100));
    }
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

  private replace(updated: Dataset): void {
    this.page.update((page) => ({
      ...page,
      results: page.results.map((row) => (row.id === updated.id ? updated : row)),
    }));
    if (this.opened()?.id === updated.id) {
      this.setOpened(updated);
    }
    this.loaded.next();
  }

  private setOpened(dataset: Dataset): void {
    this.opened.set(dataset);
    this.openedChanged.next();
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
