import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { ChangeDetectionStrategy, Component, computed, inject, signal, type WritableSignal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSlider, MatSliderThumb } from '@angular/material/slider';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import {
  PROMPT_MAX,
  REPLY_SETTINGS,
  type ConversationChange,
  type ReplySetting,
  type ReplySettingKey,
  type ReplySettings,
} from '../../data/chat.types';
import { ConversationStore } from '../../state/conversation.store';
import { ConversationsStore } from '../../state/conversations.store';

@Component({
  selector: 'app-conversation-settings',
  imports: [
    CdkTextareaAutosize,
    FormsModule,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    MatSlider,
    MatSliderThumb,
    Note,
    Term,
    TranslatePipe,
  ],
  templateUrl: './conversation-settings.html',
  styleUrl: './conversation-settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationSettings {
  private readonly store = inject(ConversationStore);
  private readonly context = inject(ConversationsStore);
  private readonly locale = inject(LocaleStore);
  private readonly reference = inject<MatDialogRef<ConversationSettings, boolean>>(MatDialogRef);

  private readonly current = this.store.conversation();

  readonly defaults = this.context.defaults;
  readonly busy = this.store.changing;

  readonly settings = REPLY_SETTINGS;
  readonly promptMax = PROMPT_MAX;

  readonly systemPrompt = signal(this.current?.system_prompt ?? '');
  readonly overrides: Readonly<Record<ReplySettingKey, WritableSignal<number | null>>> = {
    temperature: signal(this.current?.generation.temperature ?? null),
    top_p: signal(this.current?.generation.top_p ?? null),
    max_tokens: signal(this.current?.generation.max_tokens ?? null),
  };
  readonly failure = signal<ApiError | null>(null);

  readonly change = computed<ConversationChange>(() => {
    const current = this.store.conversation();
    if (current === null) {
      return {};
    }
    const generation = this.generation();
    const generationChanged = REPLY_SETTINGS.some(({ key }) => generation[key] !== current.generation[key]);
    return {
      ...(this.systemPrompt().trim() !== current.system_prompt ? { system_prompt: this.systemPrompt().trim() } : {}),
      ...(generationChanged ? { generation } : {}),
    };
  });

  readonly dirty = computed(() => Object.keys(this.change()).length > 0);

  value(setting: ReplySetting): number {
    return this.overrides[setting.key]() ?? this.projectValue(setting) ?? setting.range.min;
  }

  shown(setting: ReplySetting): string {
    return formatNumber(this.value(setting), this.locale.locale(), setting.digits);
  }

  projectShown(setting: ReplySetting): string {
    const value = this.projectValue(setting);
    return value === null ? '' : formatNumber(value, this.locale.locale(), setting.digits);
  }

  setValue(setting: ReplySetting, value: number): void {
    const factor = 10 ** setting.digits;
    const rounded = Math.round(value * factor) / factor;
    this.overrides[setting.key].set(rounded === this.projectValue(setting) ? null : rounded);
  }

  useProject(setting: ReplySetting): void {
    this.overrides[setting.key].set(null);
  }

  async save(): Promise<void> {
    if (!this.dirty()) {
      this.reference.close(false);
      return;
    }
    const failure = await this.store.change(this.change());
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }

  private projectValue(setting: ReplySetting): number | null {
    return this.defaults()?.generation[setting.key] ?? null;
  }

  private generation(): ReplySettings {
    const picked: { -readonly [Key in ReplySettingKey]?: number } = {};
    for (const { key } of REPLY_SETTINGS) {
      const value = this.overrides[key]();
      if (value !== null) {
        picked[key] = value;
      }
    }
    return picked;
  }
}
