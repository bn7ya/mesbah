import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom, type Observable } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError } from '@core/http/api.types';
import { SystemApi } from '../data/system.api';
import { TRAINING_PARTS, type Gpu, type SystemOverview } from '../data/system.types';

@Injectable()
export class SystemStore {
  private readonly api = inject(SystemApi);
  private readonly auth = inject(AuthStore);

  readonly overview = signal<SystemOverview | null>(null);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly loadError = signal<ApiError | null>(null);

  readonly canManage = computed(() => this.auth.hasAnyGroup(rolesFrom('admins')));

  readonly gpus = computed<readonly Gpu[]>(() => this.overview()?.machine.gpus ?? []);

  readonly selectedGpus = computed<readonly Gpu[]>(() => {
    const chosen = new Set(this.overview()?.selected_gpus ?? []);
    return this.gpus().filter((gpu) => chosen.has(gpu.index));
  });

  readonly trainingReady = computed(() => {
    const parts = this.overview()?.parts ?? [];
    return TRAINING_PARTS.every((name) => parts.some((part) => part.name === name && part.version !== null));
  });

  readonly torchWithoutCuda = computed(() => {
    const torch = this.overview()?.parts.find((part) => part.name === 'torch');
    return this.gpus().length > 0 && torch?.cuda === false;
  });

  async load(): Promise<void> {
    this.loading.set(true);
    this.loadError.set(null);
    try {
      this.overview.set(await firstValueFrom(this.api.overview()));
    } catch (error) {
      this.loadError.set(error as ApiError);
    } finally {
      this.loading.set(false);
    }
  }

  selectGpus(indices: readonly number[]): Promise<boolean> {
    return this.save(this.api.selectGpus({ gpus: indices }));
  }

  saveHuggingFaceToken(token: string): Promise<boolean> {
    return this.save(this.api.saveHuggingFaceToken({ token }));
  }

  removeHuggingFaceToken(): Promise<boolean> {
    return this.save(this.api.removeHuggingFaceToken());
  }

  private async save(request: Observable<SystemOverview>): Promise<boolean> {
    this.saving.set(true);
    this.error.set(null);
    try {
      this.overview.set(await firstValueFrom(request));
      return true;
    } catch (error) {
      this.error.set(error as ApiError);
      return false;
    } finally {
      this.saving.set(false);
    }
  }
}
