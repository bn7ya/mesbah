import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import {
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect, MatSelectTrigger } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { RouterLink } from '@angular/router';

import type { ApiError } from '@core/http/api.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { DESCRIPTION_MAX, NAME_MAX, PROMPT_MAX } from '../../data/projects.types';
import { ProjectsStore } from '../../state/projects.store';

@Component({
  selector: 'app-new-project',
  imports: [
    CdkTextareaAutosize,
    CompactPipe,
    FormsModule,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatOption,
    MatProgressBar,
    MatSelect,
    MatSelectTrigger,
    MatSlideToggle,
    RouterLink,
    TranslatePipe,
  ],
  templateUrl: './new-project.html',
  styleUrl: './new-project.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewProjectDialog {
  private readonly store = inject(ProjectsStore);
  private readonly reference = inject<MatDialogRef<NewProjectDialog, string>>(MatDialogRef);

  readonly models = this.store.readyModels;
  readonly loadingModels = this.store.modelsLoading;
  readonly modelsFailure = this.store.modelsError;
  readonly creating = this.store.creating;

  readonly nameMax = NAME_MAX;
  readonly descriptionMax = DESCRIPTION_MAX;
  readonly promptMax = PROMPT_MAX;

  readonly name = signal('');
  readonly description = signal('');
  readonly systemPrompt = signal('');
  readonly submitted = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly modelId = linkedSignal(() => {
    const only = this.models();
    return only.length === 1 ? only[0].id : '';
  });

  readonly selected = computed(() => this.models().find((model) => model.id === this.modelId()) ?? null);
  readonly canThink = computed(() => this.selected()?.supports_thinking ?? false);
  readonly thinking = linkedSignal(() => this.canThink());

  readonly noModel = computed(() => !this.loadingModels() && this.modelsFailure() === null && this.models().length === 0);

  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly modelInvalid = computed(() => this.submitted() && this.selected() === null);
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };
  readonly modelErrors: ErrorStateMatcher = { isErrorState: () => this.modelInvalid() };

  tryModelsAgain(): void {
    this.store.modelsAgain();
  }

  async submit(): Promise<void> {
    this.submitted.set(true);
    const model = this.selected();
    if (this.nameInvalid() || model === null) {
      return;
    }
    const result = await this.store.create({
      name: this.name().trim(),
      base_model: model.id,
      description: this.description().trim(),
      system_prompt: this.systemPrompt().trim(),
      thinking: this.thinking(),
    });
    if ('project' in result) {
      this.reference.close(result.project.id);
    } else {
      this.failure.set(result.error);
    }
  }
}
