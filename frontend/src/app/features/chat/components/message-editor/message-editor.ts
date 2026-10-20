import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterNextRender,
  computed,
  input,
  linkedSignal,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { MESSAGE_MAX } from '../../data/chat.types';

let nextId = 0;

@Component({
  selector: 'app-message-editor',
  imports: [CdkTextareaAutosize, FormsModule, MatButton, MatError, MatFormField, MatHint, MatInput, MatLabel, TranslatePipe],
  templateUrl: './message-editor.html',
  styleUrl: './message-editor.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MessageEditor {
  readonly initial = input.required<string>();
  readonly labelKey = input.required<string>();
  readonly hintKey = input<string | null>(null);
  readonly original = input<string | null>(null);
  readonly requireText = input(false);
  readonly busy = input(false);

  readonly saved = output<string>();
  readonly cancelled = output<void>();

  readonly field = viewChild.required<ElementRef<HTMLTextAreaElement>>('field');

  readonly max = MESSAGE_MAX;
  readonly originalId = `message-original-${nextId++}`;

  readonly draft = linkedSignal(() => this.initial());
  readonly showOriginal = signal(false);
  readonly submitted = signal(false);

  readonly invalid = computed(() => this.requireText() && this.submitted() && this.draft().trim() === '');
  readonly errors: ErrorStateMatcher = { isErrorState: () => this.invalid() };

  constructor() {
    afterNextRender(() => {
      const element = this.field().nativeElement;
      element.focus();
      element.setSelectionRange(element.value.length, element.value.length);
    });
  }

  save(): void {
    this.submitted.set(true);
    if (this.invalid() || this.busy()) {
      return;
    }
    this.saved.emit(this.draft());
  }

  cancel(): void {
    this.cancelled.emit();
  }
}
