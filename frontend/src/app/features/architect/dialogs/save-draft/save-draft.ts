import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';

import type { ApiError } from '@core/http/api.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import { NAME_MAX, NOTES_MAX, type Draft, type SaveDialogData } from '../../data/architect.types';
import { ArchitectStore } from '../../state/architect.store';

@Component({
  selector: 'app-save-draft',
  imports: [
    CdkTextareaAutosize,
    FormsModule,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    Note,
    TranslatePipe,
  ],
  templateUrl: './save-draft.html',
  styleUrl: './save-draft.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SaveDraftDialog {
  private readonly store = inject(ArchitectStore);
  private readonly reference = inject<MatDialogRef<SaveDraftDialog, Draft>>(MatDialogRef);

  readonly data = inject<SaveDialogData>(MAT_DIALOG_DATA);

  readonly saving = this.store.saving;

  readonly nameMax = NAME_MAX;
  readonly notesMax = NOTES_MAX;

  readonly name = signal(this.data.draft?.name ?? '');
  readonly notes = signal(this.data.draft?.notes ?? '');
  readonly submitted = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };

  async submit(): Promise<void> {
    this.submitted.set(true);
    if (this.nameInvalid()) {
      return;
    }
    const text = { name: this.name().trim(), notes: this.notes().trim() };
    const draft = this.data.draft;
    const result =
      this.data.mode === 'rename' && draft !== null ? await this.store.rename(draft, text) : await this.store.save(text);
    if ('draft' in result) {
      this.reference.close(result.draft);
    } else {
      this.failure.set(result.error);
    }
  }
}
