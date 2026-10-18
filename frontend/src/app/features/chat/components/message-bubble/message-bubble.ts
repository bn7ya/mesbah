import { Clipboard } from '@angular/cdk/clipboard';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatDivider } from '@angular/material/divider';
import { MatIcon } from '@angular/material/icon';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { formatNumber } from '@shared/format/format';
import { Term } from '@shared/term/term';
import { VersionNamePipe } from '@shared/version/version-name.pipe';
import type { Message, MessagePart } from '../../data/chat.types';
import { ConversationStore } from '../../state/conversation.store';
import { MessageEditor } from '../message-editor/message-editor';
import { ThinkingSection } from '../thinking-section/thinking-section';

const MS_PER_SECOND = 1000;

@Component({
  selector: 'app-message-bubble',
  imports: [
    DateTimePipe,
    MatDivider,
    MatIcon,
    MatIconButton,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MessageEditor,
    RouterLink,
    Term,
    ThinkingSection,
    TranslatePipe,
    VersionNamePipe,
  ],
  templateUrl: './message-bubble.html',
  styleUrl: './message-bubble.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MessageBubble {
  private readonly store = inject(ConversationStore);
  private readonly ui = inject(UiModeStore);
  private readonly locale = inject(LocaleStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly clipboard = inject(Clipboard);
  private readonly injector = inject(Injector);

  readonly message = input.required<Message>();

  readonly article = viewChild.required<ElementRef<HTMLElement>>('bubble');

  readonly editing = signal<MessagePart | null>(null);
  readonly editFrom = signal('');

  readonly expert = this.ui.expert;

  readonly isUser = computed(() => this.message().role === 'user');
  readonly live = computed(() => {
    const state = this.store.stream();
    return state !== null && state.replyId === this.message().id ? state : null;
  });
  readonly streaming = computed(() => this.message().status === 'streaming');
  readonly content = computed(() => this.live()?.content ?? this.message().content);
  readonly thinking = computed(() => this.live()?.thinking ?? this.message().thinking);
  readonly busy = computed(() => this.store.working().includes(this.message().id));
  readonly canAct = computed(
    () => this.store.canWrite() && this.message().role === 'assistant' && !this.streaming(),
  );
  readonly canCopy = computed(
    () => this.message().role === 'assistant' && !this.streaming() && this.message().content !== '',
  );
  readonly version = computed(() => this.store.versionLabel(this.message().version));

  readonly progress = computed(() => {
    const live = this.live();
    if (live !== null) {
      return this.locale.translate(`chat.stream.${live.phase}`);
    }
    return this.streaming() ? this.locale.translate('chat.stream.writing') : null;
  });

  readonly reason = computed(() => {
    const message = this.message();
    if (message.status !== 'failed') {
      return null;
    }
    const key = `errors.${message.error_code}`;
    const text = this.locale.translate(key);
    return text === key ? this.locale.translate('chat.status.failedUnknown') : text;
  });

  readonly engineNotRunning = computed(() => this.message().error_code === 'engine_unreachable');

  readonly seconds = computed(() => {
    const latency = this.message().latency_ms;
    return latency === null ? null : formatNumber(latency / MS_PER_SECOND, this.locale.locale(), 1);
  });

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  startEdit(part: MessagePart): void {
    const message = this.message();
    this.editFrom.set(part === 'content' ? message.content : message.thinking);
    this.editing.set(part);
  }

  finishEditing(): void {
    this.editing.set(null);
    afterNextRender(() => this.article().nativeElement.focus(), { injector: this.injector });
  }

  async save(part: MessagePart, text: string): Promise<void> {
    const message = this.message();
    const unchanged = part === 'content' ? text === message.content : text.trim() === message.thinking;
    if (unchanged) {
      this.finishEditing();
      return;
    }
    const failure = await this.store.edit(message, part === 'content' ? { content: text } : { thinking: text });
    if (failure === null) {
      this.finishEditing();
      this.report(this.locale.translate('chat.edit.saved'));
    } else {
      this.report(failure.message);
    }
  }

  async toggleApproved(): Promise<void> {
    const message = this.message();
    const failure = await this.store.approve(message, !message.approved);
    this.report(
      failure === null
        ? this.locale.translate(message.approved ? 'chat.approval.withdrawn' : 'chat.approval.given')
        : failure.message,
    );
  }

  async toggleTraining(): Promise<void> {
    const message = this.message();
    const failure = await this.store.edit(message, { include_in_training: !message.include_in_training });
    this.report(
      failure === null
        ? this.locale.translate(message.include_in_training ? 'chat.training.excluded' : 'chat.training.included')
        : failure.message,
    );
  }

  async restore(part: MessagePart): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: part === 'content' ? 'chat.restore.replyTitle' : 'chat.restore.thinkingTitle',
      bodyKey: part === 'content' ? 'chat.restore.replyBody' : 'chat.restore.thinkingBody',
      confirmKey: 'chat.restore.confirm',
    });
    if (!confirmed) {
      return;
    }
    const failure = await this.store.restore(this.message(), part);
    this.report(failure === null ? this.locale.translate('chat.restore.done') : failure.message);
  }

  copy(): void {
    const copied = this.clipboard.copy(this.message().content);
    this.report(this.locale.translate(copied ? 'chat.copied' : 'chat.copyFailed'));
  }

  private report(text: string): void {
    this.snackBar.open(text, undefined, { duration: 4000 });
  }
}
