import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource, toObservable } from '@angular/core/rxjs-interop';
import {
  EMPTY,
  distinctUntilChanged,
  exhaustMap,
  expand,
  firstValueFrom,
  interval,
  reduce,
  switchMap,
  tap,
  type Observable,
} from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError, Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { ActiveVersionChanges } from '@shared/version/active-version-changes';
import { VersionsApi } from '../data/versions.api';
import {
  UNFINISHED_EXPORTS,
  type ChangeMap,
  type NewExport,
  type Version,
  type VersionChange,
  type VersionChanges,
  type VersionExport,
  type VersionNode,
} from '../data/versions.types';
import { buildChangeMap } from './change-map';

const POLL_MS = 3000;

function collectPages<T>(fetch: (page: number) => Observable<Page<T>>): Observable<readonly T[]> {
  return fetch(1).pipe(
    expand((page, index) => (page.next === null ? EMPTY : fetch(index + 2))),
    reduce((all: readonly T[], page: Page<T>) => [...all, ...page.results], [] as readonly T[]),
  );
}

function buildTree(versions: readonly Version[]): readonly VersionNode[] {
  const known = new Set(versions.map((version) => version.id));
  const below = new Map<string, Version[]>();
  const roots: Version[] = [];
  for (const version of versions) {
    if (version.parent_id !== null && known.has(version.parent_id)) {
      below.set(version.parent_id, [...(below.get(version.parent_id) ?? []), version]);
    } else {
      roots.push(version);
    }
  }
  const node = (version: Version): VersionNode => ({
    version,
    children: (below.get(version.id) ?? []).map(node),
  });
  return roots.map(node);
}

@Injectable()
export class VersionsStore {
  private readonly api = inject(VersionsApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);
  private readonly changes = inject(ActiveVersionChanges);

  readonly projectId = signal<string | null>(null);
  readonly working = signal<readonly string[]>([]);
  readonly error = signal<ApiError | null>(null);

  private readonly exportsOf = signal<string | null>(null);
  private readonly changesOf = signal<string | null>(null);
  private exportsEpoch = 0;

  readonly exportsWorking = signal<readonly string[]>([]);
  readonly exportsError = signal<ApiError | null>(null);

  private readonly loaded = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => this.collect(params).pipe(tap((versions) => this.announce(versions))),
  });

  readonly versions = computed<readonly Version[]>(() => (this.loaded.hasValue() ? this.loaded.value() : []));
  readonly tree = computed(() => buildTree(this.versions()));
  readonly loading = computed(() => this.loaded.isLoading());
  readonly loadError = computed(() => this.failure(this.loaded.status() === 'error' ? this.loaded.error() : undefined));
  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  private readonly exported = rxResource({
    params: () => this.exportsOf() ?? undefined,
    stream: ({ params }) => collectPages((page) => this.api.exports(params, page)),
  });

  readonly exports = computed<readonly VersionExport[]>(() => (this.exported.hasValue() ? this.exported.value() : []));
  readonly exportsLoaded = computed(() => this.exported.hasValue());
  readonly exportsLoading = computed(() => this.exported.isLoading());
  readonly exportsLoadError = computed(() =>
    this.failure(this.exported.status() === 'error' ? this.exported.error() : undefined),
  );
  readonly unfinishedExports = computed(() => this.exports().some((row) => UNFINISHED_EXPORTS.includes(row.status)));

  private readonly unfinished$ = toObservable(this.unfinishedExports);

  private readonly changed = rxResource({
    params: () => this.changesOf() ?? undefined,
    stream: ({ params }) => this.api.changes(params),
  });

  readonly versionChanges = computed<VersionChanges | null>(() =>
    this.changed.hasValue() ? this.changed.value() : null,
  );
  readonly changeMap = computed<ChangeMap | null>(() => {
    const changes = this.versionChanges();
    return changes === null ? null : buildChangeMap(changes);
  });
  readonly changesLoading = computed(() => this.changed.isLoading());
  readonly changesLoadError = computed(() =>
    this.failure(this.changed.status() === 'error' ? this.changed.error() : undefined),
  );

  open(id: string): void {
    if (this.projectId() === id) {
      this.loaded.reload();
    } else {
      this.projectId.set(id);
    }
  }

  reload(): void {
    this.loaded.reload();
  }

  activate(version: Version): Promise<boolean> {
    return this.mutate(version.id, async () => {
      const updated = await firstValueFrom(this.api.activate(version.id));
      this.commit(
        this.versions().map((row) => (row.id === updated.id ? updated : { ...row, is_active: false })),
      );
    });
  }

  async rename(version: Version, change: VersionChange): Promise<ApiError | null> {
    this.working.update((ids) => [...ids, version.id]);
    try {
      const updated = await firstValueFrom(this.api.change(version.id, change));
      this.commit(this.versions().map((row) => (row.id === updated.id ? updated : row)));
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.working.update((ids) => ids.filter((id) => id !== version.id));
    }
  }

  remove(version: Version): Promise<boolean> {
    return this.mutate(version.id, async () => {
      await firstValueFrom(this.api.remove(version.id));
      const project = this.projectId();
      if (project !== null) {
        this.commit(await firstValueFrom(this.collect(project)));
      }
    });
  }

  showChanges(id: string): void {
    this.changesOf.set(id);
  }

  reloadChanges(): void {
    this.changed.reload();
  }

  forgetChanges(): void {
    this.changesOf.set(null);
  }

  showExports(id: string): void {
    this.exportsError.set(null);
    if (this.exportsOf() === id) {
      this.exported.reload();
    } else {
      this.exportsOf.set(id);
    }
  }

  reloadExports(): void {
    this.exported.reload();
  }

  forgetExports(): void {
    this.exportsOf.set(null);
  }

  watchExports(): Observable<void> {
    return this.unfinished$.pipe(
      distinctUntilChanged(),
      switchMap((active) => (active ? interval(POLL_MS) : EMPTY)),
      exhaustMap(() => this.refreshExports()),
    );
  }

  async createExport(version: Version, request: NewExport): Promise<ApiError | null> {
    try {
      const created = await firstValueFrom(this.api.createExport(version.id, request));
      if (this.exportsOf() === version.id) {
        this.replaceExports([created, ...this.exports()]);
      }
      return null;
    } catch (error) {
      return error as ApiError;
    }
  }

  async removeExport(row: VersionExport): Promise<boolean> {
    this.exportsWorking.update((ids) => [...ids, row.id]);
    this.exportsError.set(null);
    try {
      await firstValueFrom(this.api.removeExport(row.id));
      this.replaceExports(this.exports().filter((other) => other.id !== row.id));
      return true;
    } catch (error) {
      this.exportsError.set(error as ApiError);
      return false;
    } finally {
      this.exportsWorking.update((ids) => ids.filter((id) => id !== row.id));
    }
  }

  downloadUrl(row: VersionExport): string {
    return this.api.downloadUrl(row.id);
  }

  private collect(project: string): Observable<readonly Version[]> {
    return collectPages((page) => this.api.tree(project, page));
  }

  private async refreshExports(): Promise<void> {
    const version = this.exportsOf();
    if (version === null) {
      return;
    }
    const epoch = this.exportsEpoch;
    try {
      const latest = await firstValueFrom(collectPages((page) => this.api.exports(version, page)));
      if (epoch === this.exportsEpoch && this.exportsOf() === version) {
        this.exported.set(latest);
      }
    } catch {
      // A failed background refresh keeps the last list on screen; the next one tries again.
    }
  }

  private replaceExports(rows: readonly VersionExport[]): void {
    this.exportsEpoch += 1;
    this.exported.set(rows);
  }

  private commit(versions: readonly Version[]): void {
    this.loaded.set(versions);
    this.announce(versions);
  }

  private announce(versions: readonly Version[]): void {
    const project = this.projectId();
    const active = versions.find((version) => version.is_active);
    if (project !== null && active !== undefined) {
      this.changes.announce({ projectId: project, version: { id: active.id, number: active.number, name: active.name } });
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

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
