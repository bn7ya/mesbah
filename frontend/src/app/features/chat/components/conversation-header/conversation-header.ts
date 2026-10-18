import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  input,
  linkedSignal,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect, MatSelectTrigger } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Term } from '@shared/term/term';
import { VersionNamePipe } from '@shared/version/version-name.pipe';
import { DEFAULT_ENGINE, FOLLOW_ACTIVE, TITLE_MAX, type ConversationChange } from '../../data/chat.types';
import { ConversationSettings } from '../../dialogs/conversation-settings/conversation-settings';
import { ConversationStore } from '../../state/conversation.store';
import { ConversationsStore } from '../../state/conversations.store';

@Component({
  selector: 'app-conversation-header',
  imports: [
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSelectTrigger,
    MatSlideToggle,
    Term,
    TranslatePipe,
    VersionNamePipe,
  ],
  templateUrl: './conversation-header.html',
  styleUrl: './conversation-header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationHeader {
  private readonly store = inject(ConversationStore);
  private readonly context = inject(ConversationsStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);

  readonly listButton = input(false);

  readonly showList = output<void>();

  readonly titleField = viewChild<ElementRef<HTMLInputElement>>('titleField');

  readonly conversation = this.store.conversation;
  readonly canWrite = this.store.canWrite;
  readonly changing = this.store.changing;
  readonly versions = this.context.versions;
  readonly engines = this.context.engines;
  readonly activeVersion = this.context.activeVersion;

  readonly followActive = FOLLOW_ACTIVE;
  readonly defaultEngine = DEFAULT_ENGINE;
  readonly titleMax = TITLE_MAX;

  readonly renaming = signal(false);
  readonly draftTitle = signal('');

  readonly versionValue = linkedSignal(() => this.conversation()?.version?.id ?? FOLLOW_ACTIVE);
  readonly engineValue = linkedSignal(() => this.conversation()?.engine?.id ?? DEFAULT_ENGINE);
  readonly thinkingValue = linkedSignal(() => this.conversation()?.thinking ?? false);

  readonly pinnedVersion = computed(() => this.versions().find((version) => version.id === this.versionValue()) ?? null);
  readonly answeringVersion = computed(() => this.pinnedVersion() ?? this.activeVersion());
  readonly pinnedEngine = computed(() => this.engines().find((engine) => engine.id === this.engineValue()) ?? null);
  readonly showEngines = computed(() => this.engines().length > 1);
  readonly engineName = computed(() => this.conversation()?.engine?.name ?? null);

  startRename(): void {
    this.draftTitle.set(this.conversation()?.title ?? '');
    this.renaming.set(true);
    afterNextRender(() => this.titleField()?.nativeElement.focus(), { injector: this.injector });
  }

  cancelRename(): void {
    this.renaming.set(false);
  }

  async saveTitle(): Promise<void> {
    const title = this.draftTitle().trim();
    if (title === (this.conversation()?.title ?? '')) {
      this.renaming.set(false);
      return;
    }
    const failure = await this.store.change({ title });
    if (failure === null) {
      this.renaming.set(false);
    } else {
      this.report(failure.message);
    }
  }

  chooseVersion(value: string): void {
    const previous = this.versionValue();
    this.versionValue.set(value);
    void this.apply({ version: value === FOLLOW_ACTIVE ? null : value }, () => this.versionValue.set(previous));
  }

  chooseEngine(value: string): void {
    const previous = this.engineValue();
    this.engineValue.set(value);
    void this.apply({ engine: value === DEFAULT_ENGINE ? null : value }, () => this.engineValue.set(previous));
  }

  toggleThinking(on: boolean): void {
    const previous = this.thinkingValue();
    this.thinkingValue.set(on);
    void this.apply({ thinking: on }, () => this.thinkingValue.set(previous));
  }

  openSettings(): void {
    this.dialog.open<ConversationSettings, undefined, boolean>(ConversationSettings, {
      injector: this.injector,
      width: '38rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
  }

  private async apply(change: ConversationChange, undo: () => void): Promise<void> {
    const failure = await this.store.change(change);
    if (failure !== null) {
      undo();
      this.report(failure.message);
    }
  }

  private report(text: string): void {
    this.snackBar.open(text, undefined, { duration: 4000 });
  }
}
