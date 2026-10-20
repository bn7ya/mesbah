import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatListItem, MatListItemLine, MatListItemTitle, MatNavList } from '@angular/material/list';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { formatNumber } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import type { Conversation } from '../../data/chat.types';
import { ConversationsStore } from '../../state/conversations.store';

@Component({
  selector: 'app-conversation-list',
  imports: [
    DateTimePipe,
    MatButton,
    MatIcon,
    MatIconButton,
    MatListItem,
    MatListItemLine,
    MatListItemTitle,
    MatNavList,
    MatProgressBar,
    Note,
    RouterLink,
    Term,
    TranslatePipe,
  ],
  templateUrl: './conversation-list.html',
  styleUrl: './conversation-list.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationList {
  private readonly store = inject(ConversationsStore);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly projectId = input.required<string>();
  readonly activeId = input<string | null>(null);

  readonly chosen = output<void>();

  readonly items = this.store.items;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly creating = this.store.creating;
  readonly removing = this.store.removing;
  readonly canWrite = this.store.canWrite;
  readonly hasMore = computed(() => this.store.nextPage() !== null);
  readonly empty = computed(() => this.items().length === 0 && !this.loading() && this.error() === null);

  title(conversation: Conversation): string {
    return conversation.title || this.locale.translate('chat.list.untitled');
  }

  count(conversation: Conversation): string {
    return formatNumber(conversation.message_count ?? 0, this.locale.locale());
  }

  more(): void {
    this.store.more();
  }

  tryAgain(): void {
    this.store.reload();
  }

  async create(): Promise<void> {
    const result = await this.store.create();
    if ('conversation' in result) {
      await this.router.navigate(['/projects', this.projectId(), 'chat', result.conversation.id]);
      this.chosen.emit();
    } else {
      this.report(result.error.message);
    }
  }

  async remove(conversation: Conversation): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'chat.remove.title',
      bodyKey: 'chat.remove.body',
      confirmKey: 'chat.remove.confirm',
      values: { title: this.title(conversation) },
      destructive: true,
    });
    if (!confirmed) {
      return;
    }
    const failure = await this.store.remove(conversation);
    if (failure !== null) {
      this.report(failure.message);
      return;
    }
    this.report(this.locale.translate('chat.remove.done'));
    if (conversation.id === this.activeId()) {
      await this.router.navigate(['/projects', this.projectId(), 'chat']);
    }
  }

  private report(text: string): void {
    this.snackBar.open(text, undefined, { duration: 4000 });
  }
}
