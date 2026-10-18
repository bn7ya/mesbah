import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { EMPTY, expand, firstValueFrom, reduce, tap, type Observable } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError, Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { ActiveVersionChanges } from '@shared/version/active-version-changes';
import { VersionsApi } from '../data/versions.api';
import type { Version, VersionChange, VersionNode } from '../data/versions.types';

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

  private readonly loaded = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => this.collect(params).pipe(tap((versions) => this.announce(versions))),
  });

  readonly versions = computed<readonly Version[]>(() => (this.loaded.hasValue() ? this.loaded.value() : []));
  readonly tree = computed(() => buildTree(this.versions()));
  readonly loading = computed(() => this.loaded.isLoading());
  readonly loadError = computed(() => this.failure(this.loaded.status() === 'error' ? this.loaded.error() : undefined));
  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

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

  private collect(project: string): Observable<readonly Version[]> {
    return this.api.tree(project, 1).pipe(
      expand((page, index) => (page.next === null ? EMPTY : this.api.tree(project, index + 2))),
      reduce((all: readonly Version[], page: Page<Version>) => [...all, ...page.results], [] as readonly Version[]),
    );
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
