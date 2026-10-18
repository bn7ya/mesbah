import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { ChangeDetectionStrategy, Component, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatHint } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { MESSAGE_MAX } from '../../data/chat.types';
import { ConversationStore } from '../../state/conversation.store';

@Component({
  selector: 'app-composer',
  imports: [CdkTextareaAutosize, FormsModule, MatButton, MatFormField, MatHint, MatIcon, MatInput, TranslatePipe],
  templateUrl: './composer.html',
  styleUrl: './composer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Composer {
  private readonly store = inject(ConversationStore);

  readonly field = viewChild<ElementRef<HTMLTextAreaElement>>('field');

  readonly canWrite = this.store.canWrite;
  readonly ready = this.store.ready;
  readonly sending = this.store.sending;
  readonly failure = this.store.sendError;

  readonly max = MESSAGE_MAX;
  readonly draft = signal('');
  readonly blank = computed(() => this.draft().trim() === '');

  pressed(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void this.send();
    }
  }

  async send(): Promise<void> {
    if (this.blank() || this.sending() || !this.ready()) {
      return;
    }
    const content = this.draft();
    this.draft.set('');
    this.field()?.nativeElement.focus();
    const started = await this.store.send(content);
    if (!started) {
      this.draft.update((current) => (current === '' ? content : current));
    }
  }

  stop(): void {
    void this.store.stop();
    this.field()?.nativeElement.focus();
  }
}
