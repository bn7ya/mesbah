import { BreakpointObserver } from '@angular/cdk/layout';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatSidenav, MatSidenavContainer, MatSidenavContent } from '@angular/material/sidenav';
import { RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Composer } from '../../components/composer/composer';
import { ConversationHeader } from '../../components/conversation-header/conversation-header';
import { ConversationList } from '../../components/conversation-list/conversation-list';
import { MessageList } from '../../components/message-list/message-list';
import { ConversationStore } from '../../state/conversation.store';
import { ConversationsStore } from '../../state/conversations.store';

// Mirrors $screen-md in src/styles/_layout.scss: a media query in code cannot read the Sass variable.
const WIDE = '(min-width: 48rem)';

@Component({
  selector: 'app-chat-page',
  imports: [
    Composer,
    ConversationHeader,
    ConversationList,
    MatButton,
    MatIcon,
    MatSidenav,
    MatSidenavContainer,
    MatSidenavContent,
    MessageList,
    RouterLink,
    TranslatePipe,
  ],
  templateUrl: './chat.html',
  styleUrl: './chat.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatPage {
  private readonly conversations = inject(ConversationsStore);
  private readonly store = inject(ConversationStore);

  readonly projectId = input.required<string>();
  readonly conversationId = input<string>();

  readonly error = this.store.error;

  readonly wide = toSignal(
    inject(BreakpointObserver)
      .observe(WIDE)
      .pipe(map((state) => state.matches)),
    { initialValue: false },
  );

  readonly listOpen = signal(false);

  constructor() {
    effect(() => {
      const id = this.projectId();
      untracked(() => this.conversations.open(id));
    });
    effect(() => {
      const id = this.conversationId() ?? null;
      untracked(() => this.store.open(id));
    });
    inject(DestroyRef).onDestroy(() => this.store.leave());
  }

  tryAgain(): void {
    this.store.reload();
  }
}
