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
import { MatError, MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';

import type { ApiError } from '@core/http/api.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import type { EditDialogData } from '../../data/datasets.types';
import { DatasetsStore } from '../../state/datasets.store';

@Component({
  selector: 'app-dataset-edit',
  imports: [
    FormsModule,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatInput,
    MatLabel,
    Note,
    TranslatePipe,
  ],
  templateUrl: './dataset-edit.html',
  styleUrl: './dataset-edit.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DatasetEditDialog {
  private readonly store = inject(DatasetsStore);
  private readonly reference = inject<MatDialogRef<DatasetEditDialog, boolean>>(MatDialogRef);
  private readonly data = inject<EditDialogData>(MAT_DIALOG_DATA);

  readonly name = signal(this.data.dataset.name);
  readonly description = signal(this.data.dataset.description);
  readonly submitted = signal(false);
  readonly saving = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };

  async save(): Promise<void> {
    this.submitted.set(true);
    if (this.nameInvalid()) {
      return;
    }
    this.saving.set(true);
    const failure = await this.store.update(this.data.dataset, {
      name: this.name().trim(),
      description: this.description().trim(),
    });
    this.saving.set(false);
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }
}
