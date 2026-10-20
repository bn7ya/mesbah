import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { exhaustMap, firstValueFrom, interval, type Observable } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { ServingApi } from '../data/serving.api';
import {
  EXAMPLE_SLUG,
  KEYS_PAGE_SIZE,
  POLL_MS,
  type ApiKey,
  type Engine,
  type EngineChange,
  type KeyResult,
  type NewEngine,
} from '../data/serving.types';

@Injectable()
export class ServingStore {
  private readonly api = inject(ServingApi);
  private readonly auth = inject(AuthStore);

  private changes = 0;

  readonly engines = signal<readonly Engine[]>([]);
  readonly loading = signal(false);
  readonly loaded = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly working = signal<readonly string[]>([]);
  readonly saving = signal(false);

  readonly keys = signal<Page<ApiKey>>(EMPTY_PAGE);
  readonly keysPageIndex = signal(0);
  readonly keysPageSize = signal(KEYS_PAGE_SIZE);
  readonly keysLoading = signal(false);
  readonly keysError = signal<ApiError | null>(null);
  readonly keyWorking = signal<readonly string[]>([]);
  readonly creatingKey = signal(false);

  private readonly slugs = rxResource({ stream: () => this.api.exampleSlugs() });

  readonly canManage = computed(() => this.auth.hasAnyGroup(rolesFrom('admins')));
  readonly canTrain = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  readonly builtin = computed(() => this.engines().find((engine) => engine.kind === 'builtin') ?? null);
  readonly others = computed(() => {
    const rest = this.engines().filter((engine) => engine.kind !== 'builtin');
    return [...rest.filter((engine) => engine.is_default), ...rest.filter((engine) => !engine.is_default)];
  });

  readonly exampleSlug = computed(() => (this.slugs.hasValue() ? (this.slugs.value()[0] ?? EXAMPLE_SLUG) : EXAMPLE_SLUG));

  async visit(): Promise<void> {
    this.engines.set([]);
    this.keys.set(EMPTY_PAGE);
    this.loaded.set(false);
    this.slugs.reload();
    await Promise.all([this.load(), this.canTrain() ? this.loadKeys(0) : undefined]);
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      await this.fetch();
    } catch (error) {
      this.error.set(error as ApiError);
    } finally {
      this.loading.set(false);
    }
  }

  watch(): Observable<void> {
    return interval(POLL_MS).pipe(exhaustMap(() => this.refresh()));
  }

  async connect(engine: NewEngine): Promise<ApiError | null> {
    this.saving.set(true);
    try {
      await firstValueFrom(this.api.connect(engine));
      this.changes++;
      await this.refresh();
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.saving.set(false);
    }
  }

  async save(engine: Engine, change: EngineChange): Promise<ApiError | null> {
    this.saving.set(true);
    try {
      this.replace(await firstValueFrom(this.api.change(engine.id, change)));
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.saving.set(false);
    }
  }

  change(engine: Engine, change: EngineChange): Promise<boolean> {
    return this.mutate(engine.id, async () => {
      this.replace(await firstValueFrom(this.api.change(engine.id, change)));
    });
  }

  unload(engine: Engine): Promise<boolean> {
    return this.mutate(engine.id, async () => {
      this.replace(await firstValueFrom(this.api.unload(engine.id)));
    });
  }

  disconnect(engine: Engine): Promise<boolean> {
    return this.mutate(engine.id, async () => {
      await firstValueFrom(this.api.disconnect(engine.id));
      this.changes++;
      this.engines.update((engines) => engines.filter((row) => row.id !== engine.id));
      await this.refresh();
    });
  }

  async loadKeys(pageIndex = this.keysPageIndex(), pageSize = this.keysPageSize()): Promise<void> {
    this.keysLoading.set(true);
    this.keysError.set(null);
    try {
      this.keys.set(await firstValueFrom(this.api.keys({ page: pageIndex + 1, page_size: pageSize })));
      this.keysPageIndex.set(pageIndex);
      this.keysPageSize.set(pageSize);
    } catch (error) {
      this.keysError.set(error as ApiError);
    } finally {
      this.keysLoading.set(false);
    }
  }

  async createKey(name: string): Promise<KeyResult> {
    this.creatingKey.set(true);
    try {
      const key = await firstValueFrom(this.api.createKey(name));
      void this.loadKeys(0);
      return { key };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.creatingKey.set(false);
    }
  }

  async revokeKey(key: ApiKey): Promise<boolean> {
    this.keyWorking.update((ids) => [...ids, key.id]);
    this.keysError.set(null);
    try {
      await firstValueFrom(this.api.revokeKey(key.id));
      await this.loadKeys(this.indexAfterRevoking());
      return true;
    } catch (error) {
      this.keysError.set(error as ApiError);
      return false;
    } finally {
      this.keyWorking.update((ids) => ids.filter((working) => working !== key.id));
    }
  }

  private async fetch(): Promise<void> {
    const stamp = this.changes;
    const page = await firstValueFrom(this.api.engines());
    if (stamp === this.changes) {
      this.engines.set(page.results);
    }
    this.loaded.set(true);
  }

  private async refresh(): Promise<void> {
    try {
      await this.fetch();
    } catch {
      // A failed background refresh keeps the last state on screen; the next one tries again.
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

  private replace(updated: Engine): void {
    this.changes++;
    this.engines.update((engines) =>
      engines.map((row) => {
        if (row.id === updated.id) {
          return updated;
        }
        return updated.is_default && row.is_default ? { ...row, is_default: false } : row;
      }),
    );
  }

  private indexAfterRevoking(): number {
    const remaining = this.keys().count - 1;
    const lastIndex = Math.max(0, Math.ceil(remaining / this.keysPageSize()) - 1);
    return Math.min(this.keysPageIndex(), lastIndex);
  }
}
