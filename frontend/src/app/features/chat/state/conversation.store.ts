import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { firstValueFrom, last, repeat, take, takeWhile, type Observable, type Subscription } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import type { VersionLabel } from '@shared/version/version.types';
import { ChatApi } from '../data/chat.api';
import {
  SETTLE_ATTEMPTS,
  SETTLE_DELAY_MS,
  type Conversation,
  type ConversationChange,
  type Message,
  type MessageChange,
  type MessagePart,
  type NamedRef,
  type ReplyEvent,
  type StreamState,
} from '../data/chat.types';
import { collectPages } from './collect-pages';
import { ConversationsStore } from './conversations.store';

@Injectable()
export class ConversationStore {
  private readonly api = inject(ChatApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);
  private readonly list = inject(ConversationsStore);

  private subscription: Subscription | null = null;
  private resolveSend: ((started: boolean) => void) | null = null;

  readonly conversationId = signal<string | null>(null);
  readonly stream = signal<StreamState | null>(null);
  readonly sending = signal(false);
  readonly sendError = signal<ApiError | null>(null);
  readonly working = signal<readonly string[]>([]);
  readonly changing = signal(false);

  private readonly conversationLoaded = rxResource({
    params: () => this.conversationId() ?? undefined,
    stream: ({ params }) => this.api.conversation(params),
  });

  private readonly messagesLoaded = rxResource({
    params: () => this.conversationId() ?? undefined,
    stream: ({ params }) => collectPages((page) => this.api.messages(params, page)),
  });

  readonly conversation = computed<Conversation | null>(() =>
    this.conversationLoaded.hasValue() ? this.conversationLoaded.value() : null,
  );
  readonly messages = computed<readonly Message[]>(() =>
    this.messagesLoaded.hasValue() ? this.messagesLoaded.value() : [],
  );
  readonly loading = computed(
    () =>
      (this.conversationLoaded.isLoading() && !this.conversationLoaded.hasValue()) ||
      (this.messagesLoaded.isLoading() && !this.messagesLoaded.hasValue()),
  );
  readonly ready = computed(() => this.conversation() !== null && this.messagesLoaded.hasValue());
  readonly error = computed(
    () =>
      this.failure(this.conversationLoaded.status() === 'error' ? this.conversationLoaded.error() : undefined) ??
      this.failure(this.messagesLoaded.status() === 'error' ? this.messagesLoaded.error() : undefined),
  );
  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('reviewers')));

  open(id: string | null): void {
    if (this.conversationId() === id) {
      if (id !== null && !this.sending()) {
        this.conversationLoaded.reload();
        this.messagesLoaded.reload();
      }
      return;
    }
    this.leave();
    this.conversationId.set(id);
  }

  reload(): void {
    this.conversationLoaded.reload();
    this.messagesLoaded.reload();
  }

  leave(): void {
    this.subscription?.unsubscribe();
    this.subscription = null;
    this.endStream();
    this.sendError.set(null);
  }

  versionLabel(version: NamedRef | null): VersionLabel | null {
    const known = version === null ? undefined : this.list.versions().find((row) => row.id === version.id);
    return known === undefined ? null : { id: known.id, number: known.number, name: known.name };
  }

  send(content: string): Promise<boolean> {
    const id = this.conversationId();
    if (id === null || this.sending() || content.trim() === '') {
      return Promise.resolve(false);
    }
    this.sending.set(true);
    this.sendError.set(null);
    return new Promise<boolean>((resolve) => {
      this.resolveSend = resolve;
      this.subscription = this.api.reply(id, content).subscribe({
        next: (event) => this.apply(id, event),
        error: (error: ApiError) => void this.interrupted(id, error),
        complete: () => void this.ended(id),
      });
    });
  }

  async stop(): Promise<void> {
    const id = this.conversationId();
    if (id === null || !this.sending()) {
      return;
    }
    const written = this.stream();
    this.subscription?.unsubscribe();
    this.subscription = null;
    this.endStream();
    if (written === null) {
      this.messagesLoaded.reload();
      return;
    }
    const placeholder = this.messages().find((message) => message.id === written.replyId);
    if (placeholder !== undefined) {
      this.replaceMessage({
        ...placeholder,
        status: 'stopped',
        content: written.content,
        thinking: written.thinking.trim(),
      });
    }
    await this.settle(id, written.replyId);
    await this.refresh(id);
  }

  edit(message: Message, change: MessageChange): Promise<ApiError | null> {
    return this.mutate(message, () => this.api.edit(message.id, { seen: message.updated_at, ...change }));
  }

  restore(message: Message, part: MessagePart): Promise<ApiError | null> {
    return this.mutate(message, () => this.api.restore(message.id, part, message.updated_at));
  }

  approve(message: Message, approved: boolean): Promise<ApiError | null> {
    return this.mutate(message, () => this.api.approve(message.id, approved));
  }

  async change(change: ConversationChange): Promise<ApiError | null> {
    const id = this.conversationId();
    if (id === null) {
      return null;
    }
    this.changing.set(true);
    try {
      const updated = await firstValueFrom(this.api.change(id, change));
      this.conversationLoaded.set(updated);
      this.list.replace(this.withCount(updated));
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.changing.set(false);
    }
  }

  private apply(id: string, event: ReplyEvent): void {
    if (this.conversationId() !== id) {
      return;
    }
    switch (event.kind) {
      case 'start':
        this.messagesLoaded.update((rows) => [...(rows ?? []), event.asked, event.reply]);
        this.stream.set({ replyId: event.reply.id, phase: 'loading', thinking: '', content: '', engine: '' });
        this.resolveSend?.(true);
        this.resolveSend = null;
        return;
      case 'ready':
        this.stream.update((state) => (state === null ? null : { ...state, phase: 'writing', engine: event.engine }));
        return;
      case 'thinking':
        this.stream.update((state) =>
          state === null ? null : { ...state, phase: 'thinking', thinking: state.thinking + event.text },
        );
        return;
      case 'content':
        this.stream.update((state) =>
          state === null ? null : { ...state, phase: 'writing', content: state.content + event.text },
        );
        return;
      case 'done':
      case 'error':
        this.replaceMessage(event.reply);
        this.subscription = null;
        this.endStream();
        void this.refresh(id);
        return;
    }
  }

  private async interrupted(id: string, error: ApiError): Promise<void> {
    const replyId = this.stream()?.replyId ?? null;
    this.subscription = null;
    this.endStream();
    this.sendError.set(error);
    if (replyId !== null) {
      await this.settle(id, replyId);
      await this.refresh(id);
    }
  }

  private async ended(id: string): Promise<void> {
    if (!this.sending()) {
      return;
    }
    const replyId = this.stream()?.replyId ?? null;
    this.subscription = null;
    this.endStream();
    if (replyId !== null) {
      await this.settle(id, replyId);
      await this.refresh(id);
    }
  }

  private endStream(): void {
    this.resolveSend?.(false);
    this.resolveSend = null;
    this.stream.set(null);
    this.sending.set(false);
  }

  private settled(messageId: string): Observable<Message> {
    return this.api.message(messageId).pipe(
      repeat({ delay: SETTLE_DELAY_MS }),
      takeWhile((message) => message.status === 'streaming', true),
      take(SETTLE_ATTEMPTS),
      last(),
    );
  }

  private async settle(conversationId: string, messageId: string): Promise<void> {
    try {
      const saved = await firstValueFrom(this.settled(messageId));
      if (this.conversationId() === conversationId && saved.status !== 'streaming') {
        this.replaceMessage(saved);
      }
    } catch (error) {
      this.sendError.set(error as ApiError);
    }
  }

  private async refresh(id: string): Promise<void> {
    try {
      const updated = await firstValueFrom(this.api.conversation(id));
      if (this.conversationId() === id) {
        this.conversationLoaded.set(updated);
        this.list.replace(this.withCount(updated));
      }
    } catch {
      // The header keeps the title it had; the list refreshes the next time it opens.
    }
  }

  private async mutate(message: Message, call: () => Observable<Message>): Promise<ApiError | null> {
    this.working.update((ids) => [...ids, message.id]);
    try {
      this.replaceMessage(await firstValueFrom(call()));
      return null;
    } catch (error) {
      const failure = error as ApiError;
      if (failure.code === 'message_changed') {
        await this.reloadMessage(message.id);
      }
      return failure;
    } finally {
      this.working.update((ids) => ids.filter((id) => id !== message.id));
    }
  }

  private async reloadMessage(id: string): Promise<void> {
    try {
      this.replaceMessage(await firstValueFrom(this.api.message(id)));
    } catch {
      // The edit's own failure is the one reported.
    }
  }

  private replaceMessage(message: Message): void {
    this.messagesLoaded.update((rows) => (rows ?? []).map((row) => (row.id === message.id ? message : row)));
  }

  private withCount(conversation: Conversation): Conversation {
    return { ...conversation, message_count: this.messagesLoaded.hasValue() ? this.messages().length : null };
  }

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
