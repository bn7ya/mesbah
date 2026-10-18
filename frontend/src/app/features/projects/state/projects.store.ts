import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { ProjectsApi } from '../data/projects.api';
import type { CreateResult, ModelOption, NewProject, Project } from '../data/projects.types';

const PAGE_SIZE = 24;

@Injectable()
export class ProjectsStore {
  private readonly api = inject(ProjectsApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);

  readonly page = signal<Page<Project>>(EMPTY_PAGE);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(PAGE_SIZE);
  readonly loading = signal(false);
  readonly creating = signal(false);
  readonly error = signal<ApiError | null>(null);

  private readonly models = rxResource({ stream: () => this.api.readyModels() });

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  readonly readyModels = computed<readonly ModelOption[]>(() => (this.models.hasValue() ? this.models.value() : []));
  readonly modelsLoading = computed(() => this.models.isLoading());
  readonly modelsError = computed(() => this.failure(this.models.status() === 'error' ? this.models.error() : undefined));

  visit(): Promise<void> {
    this.page.set(EMPTY_PAGE);
    return this.load(0);
  }

  async load(pageIndex = this.pageIndex(), pageSize = this.pageSize()): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    this.models.reload();
    try {
      const page = await firstValueFrom(this.api.list({ page: pageIndex + 1, page_size: pageSize }));
      this.page.set(page);
      this.pageIndex.set(pageIndex);
      this.pageSize.set(pageSize);
    } catch (error) {
      this.error.set(error as ApiError);
    } finally {
      this.loading.set(false);
    }
  }

  modelsAgain(): void {
    this.models.reload();
  }

  async create(project: NewProject): Promise<CreateResult> {
    this.creating.set(true);
    try {
      return { project: await firstValueFrom(this.api.create(project)) };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.creating.set(false);
    }
  }

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
