import { CdkObserveContent } from '@angular/cdk/observers';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  linkedSignal,
  viewChild,
} from '@angular/core';
import { MatMiniFabButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { PinSource } from '../../data/chat.types';
import { ConversationStore } from '../../state/conversation.store';
import { MessageBubble } from '../message-bubble/message-bubble';

const NEAR_BOTTOM = 48;

@Component({
  selector: 'app-message-list',
  imports: [CdkObserveContent, MatIcon, MatMiniFabButton, MatProgressBar, MessageBubble, TranslatePipe],
  templateUrl: './message-list.html',
  styleUrl: './message-list.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MessageList {
  private readonly store = inject(ConversationStore);

  readonly scroller = viewChild.required<ElementRef<HTMLElement>>('scroller');

  readonly messages = this.store.messages;
  readonly loading = this.store.loading;

  readonly empty = computed(() => this.store.ready() && this.messages().length === 0);

  readonly pinned = linkedSignal<PinSource, boolean>({
    source: () => ({ id: this.store.conversationId(), started: this.store.sending() }),
    computation: (now, previous) =>
      previous !== undefined && previous.source.id === now.id && !now.started ? previous.value : true,
  });

  scrolled(): void {
    const element = this.scroller().nativeElement;
    this.pinned.set(element.scrollHeight - element.scrollTop - element.clientHeight < NEAR_BOTTOM);
  }

  changed(): void {
    if (this.pinned()) {
      this.toBottom();
    } else {
      this.scrolled();
    }
  }

  jump(): void {
    this.pinned.set(true);
    this.toBottom();
  }

  private toBottom(): void {
    const element = this.scroller().nativeElement;
    element.scrollTop = element.scrollHeight;
  }
}
