import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { ChatApi } from '../data/chat.api';
import type {
  Conversation,
  CreateConversationResult,
  EngineOption,
  ProjectDefaults,
  VersionOption,
} from '../data/chat.types';
import { collectPages } from './collect-pages';

function newestFirst(conversations: readonly Conversation[]): readonly Conversation[] {
  return [...conversations].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
}

@Injectable()
export class ConversationsStore {
  private readonly api = inject(ChatApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);

  readonly projectId = signal<string | null>(null);
  readonly items = signal<readonly Conversation[]>([]);
  readonly nextPage = signal<number | null>(null);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly creating = signal(false);
  readonly removing = signal<readonly string[]>([]);

  private readonly defaultsLoaded = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => this.api.project(params),
  });

  private readonly versionsLoaded = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: ({ params }) => collectPages((page) => this.api.versions(params, page)),
  });

  private readonly enginesLoaded = rxResource({
    params: () => this.projectId() ?? undefined,
    stream: () => this.api.engines(),
  });

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('reviewers')));

  readonly defaults = computed<ProjectDefaults | null>(() =>
    this.defaultsLoaded.hasValue() ? this.defaultsLoaded.value() : null,
  );
  readonly versions = computed<readonly VersionOption[]>(() =>
    this.versionsLoaded.hasValue() ? this.versionsLoaded.value() : [],
  );
  readonly engines = computed<readonly EngineOption[]>(() =>
    this.enginesLoaded.hasValue() ? this.enginesLoaded.value() : [],
  );
  readonly activeVersion = computed<VersionOption | null>(
    () => this.versions().find((version) => version.is_active) ?? null,
  );

  open(projectId: string): void {
    if (this.projectId() === projectId) {
      this.defaultsLoaded.reload();
      this.versionsLoaded.reload();
      this.enginesLoaded.reload();
    } else {
      this.items.set([]);
      this.nextPage.set(null);
      this.projectId.set(projectId);
    }
    void this.load(projectId, 1);
  }

  reload(): void {
    const projectId = this.projectId();
    if (projectId !== null) {
      void this.load(projectId, 1);
    }
  }

  more(): void {
    const projectId = this.projectId();
    const page = this.nextPage();
    if (projectId !== null && page !== null && !this.loading()) {
      void this.load(projectId, page);
    }
  }

  async create(): Promise<CreateConversationResult> {
    const project = this.projectId();
    if (project === null) {
      return { error: { code: 'unknown', message: this.locale.translate('errors.generic') } };
    }
    this.creating.set(true);
    try {
      const conversation = await firstValueFrom(this.api.create({ project }));
      this.items.update((current) => [conversation, ...current]);
      return { conversation };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.creating.set(false);
    }
  }

  async remove(conversation: Conversation): Promise<ApiError | null> {
    this.removing.update((ids) => [...ids, conversation.id]);
    try {
      await firstValueFrom(this.api.remove(conversation.id));
      this.items.update((current) => current.filter((row) => row.id !== conversation.id));
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.removing.update((ids) => ids.filter((id) => id !== conversation.id));
    }
  }

  replace(conversation: Conversation): void {
    this.items.update((current) => {
      const previous = current.find((row) => row.id === conversation.id);
      if (previous === undefined) {
        return current;
      }
      const count = conversation.message_count ?? previous.message_count;
      return newestFirst(
        current.map((row) => (row.id === conversation.id ? { ...conversation, message_count: count } : row)),
      );
    });
  }

  private async load(projectId: string, page: number): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const result = await firstValueFrom(this.api.conversations(projectId, page));
      if (this.projectId() !== projectId) {
        return;
      }
      this.items.update((current) => (page === 1 ? result.results : [...current, ...result.results]));
      this.nextPage.set(result.next === null ? null : page + 1);
    } catch (error) {
      if (this.projectId() === projectId) {
        this.error.set(error as ApiError);
      }
    } finally {
      this.loading.set(false);
    }
  }
}
