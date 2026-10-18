import { Injectable, computed, inject, linkedSignal, signal } from '@angular/core';
import { rxResource, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { ActiveVersionChanges } from '@shared/version/active-version-changes';
import type { VersionLabel } from '@shared/version/version.types';
import { ProjectsApi } from '../data/projects.api';
import type { Project, ProjectChange } from '../data/projects.types';

@Injectable()
export class ProjectStore {
  private readonly api = inject(ProjectsApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);
  private readonly versionChanges = inject(ActiveVersionChanges);

  readonly projectId = signal<string | null>(null);
  readonly saving = signal(false);

  private readonly loaded = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => this.api.find(params),
  });

  readonly project = computed<Project | null>(() => (this.loaded.hasValue() ? this.loaded.value() : null));
  readonly loading = computed(() => this.loaded.isLoading());
  readonly error = computed(() => this.failure(this.loaded.status() === 'error' ? this.loaded.error() : undefined));

  readonly activeVersion = linkedSignal<VersionLabel | null>(() => this.project()?.active_version ?? null);

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  constructor() {
    this.versionChanges.changes.pipe(takeUntilDestroyed()).subscribe((change) => {
      if (change.projectId === this.projectId()) {
        this.activeVersion.set(change.version);
      }
    });
  }

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

  async save(change: ProjectChange): Promise<ApiError | null> {
    const project = this.project();
    if (project === null) {
      return null;
    }
    this.saving.set(true);
    try {
      this.loaded.set(await firstValueFrom(this.api.change(project.id, change)));
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.saving.set(false);
    }
  }

  async remove(): Promise<ApiError | null> {
    const project = this.project();
    if (project === null) {
      return null;
    }
    this.saving.set(true);
    try {
      await firstValueFrom(this.api.remove(project.id));
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.saving.set(false);
    }
  }

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
