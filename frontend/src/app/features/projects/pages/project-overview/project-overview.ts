import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal, signal, type WritableSignal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatDialog } from '@angular/material/dialog';
import { MatDivider } from '@angular/material/divider';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSlider, MatSliderThumb } from '@angular/material/slider';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { CompactPipe } from '@shared/format/compact.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { formatNumber } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import {
  DESCRIPTION_MAX,
  GENERATION_SETTINGS,
  NAME_MAX,
  PROMPT_MAX,
  type GenerationKey,
  type GenerationSetting,
  type Project,
  type ProjectChange,
} from '../../data/projects.types';
import { ProjectStore } from '../../state/project.store';

@Component({
  selector: 'app-project-overview',
  imports: [
    CdkTextareaAutosize,
    CompactPipe,
    DateTimePipe,
    FormsModule,
    MatButton,
    MatCard,
    MatDivider,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatSlider,
    MatSliderThumb,
    MatSlideToggle,
    Note,
    RouterLink,
    Term,
    TranslatePipe,
  ],
  templateUrl: './project-overview.html',
  styleUrl: './project-overview.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProjectOverview {
  private readonly store = inject(ProjectStore);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly project = this.store.project;
  readonly canWrite = this.store.canWrite;
  readonly saving = this.store.saving;

  readonly settings = GENERATION_SETTINGS;
  readonly nameMax = NAME_MAX;
  readonly descriptionMax = DESCRIPTION_MAX;
  readonly promptMax = PROMPT_MAX;

  readonly name = this.draft((project) => project.name, '');
  readonly description = this.draft((project) => project.description, '');
  readonly systemPrompt = this.draft((project) => project.system_prompt, '');
  readonly thinking = this.draft((project) => project.thinking, false);
  readonly generation: Readonly<Record<GenerationKey, WritableSignal<number>>> = {
    temperature: this.draft((project) => project.generation.temperature, 0),
    top_p: this.draft((project) => project.generation.top_p, 0),
    max_tokens: this.draft((project) => project.generation.max_tokens, 0),
  };

  readonly aboutSubmitted = signal(false);
  readonly aboutFailure = signal<ApiError | null>(null);
  readonly replyFailure = signal<ApiError | null>(null);
  readonly removeFailure = signal<ApiError | null>(null);

  readonly nameInvalid = computed(() => this.aboutSubmitted() && this.name().trim() === '');
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };

  readonly canThink = computed(() => this.project()?.base_model?.supports_thinking ?? false);

  readonly aboutDirty = computed(() => {
    const project = this.project();
    return project !== null && (this.name().trim() !== project.name || this.description().trim() !== project.description);
  });

  readonly replyDirty = computed(() => {
    const project = this.project();
    return (
      project !== null &&
      (this.systemPrompt() !== project.system_prompt ||
        this.thinking() !== project.thinking ||
        GENERATION_SETTINGS.some((setting) => this.generation[setting.key]() !== project.generation[setting.key]))
    );
  });

  value(setting: GenerationSetting): string {
    return formatNumber(this.generation[setting.key](), this.locale.locale(), setting.digits);
  }

  setValue(setting: GenerationSetting, value: number): void {
    const factor = 10 ** setting.digits;
    this.generation[setting.key].set(Math.round(value * factor) / factor);
  }

  resetAbout(): void {
    const project = this.project();
    if (project !== null) {
      this.name.set(project.name);
      this.description.set(project.description);
    }
    this.aboutSubmitted.set(false);
    this.aboutFailure.set(null);
  }

  resetReply(): void {
    const project = this.project();
    if (project !== null) {
      this.systemPrompt.set(project.system_prompt);
      this.thinking.set(project.thinking);
      for (const setting of GENERATION_SETTINGS) {
        this.generation[setting.key].set(project.generation[setting.key]);
      }
    }
    this.replyFailure.set(null);
  }

  async saveAbout(): Promise<void> {
    const project = this.project();
    this.aboutSubmitted.set(true);
    if (project === null || this.nameInvalid()) {
      return;
    }
    const name = this.name().trim();
    const description = this.description().trim();
    const failure = await this.store.save({
      ...(name !== project.name ? { name } : {}),
      ...(description !== project.description ? { description } : {}),
    });
    this.aboutFailure.set(failure);
    if (failure === null) {
      this.aboutSubmitted.set(false);
      this.report('projects.overview.saved');
    }
  }

  async saveReply(): Promise<void> {
    const project = this.project();
    if (project === null) {
      return;
    }
    const generation = {
      temperature: this.generation.temperature(),
      top_p: this.generation.top_p(),
      max_tokens: this.generation.max_tokens(),
    };
    const generationChanged = GENERATION_SETTINGS.some((setting) => generation[setting.key] !== project.generation[setting.key]);
    const change: ProjectChange = {
      ...(this.systemPrompt() !== project.system_prompt ? { system_prompt: this.systemPrompt() } : {}),
      ...(this.thinking() !== project.thinking ? { thinking: this.thinking() } : {}),
      ...(generationChanged ? { generation } : {}),
    };
    const failure = await this.store.save(change);
    this.replyFailure.set(failure);
    if (failure === null) {
      this.report('projects.overview.saved');
    }
  }

  async remove(): Promise<void> {
    const project = this.project();
    if (project === null) {
      return;
    }
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'projects.overview.remove.confirmTitle',
      bodyKey: 'projects.overview.remove.confirmBody',
      confirmKey: 'projects.overview.remove.confirm',
      values: { name: project.name },
      destructive: true,
    });
    if (!confirmed) {
      return;
    }
    const failure = await this.store.remove();
    this.removeFailure.set(failure);
    if (failure === null) {
      this.report('projects.overview.remove.done');
      await this.router.navigate(['/projects']);
    }
  }

  private draft<T extends string | number | boolean>(read: (project: Project) => T, fallback: T): WritableSignal<T> {
    return linkedSignal({
      source: () => {
        const project = this.project();
        return project === null ? fallback : read(project);
      },
      computation: (value) => value,
    });
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
