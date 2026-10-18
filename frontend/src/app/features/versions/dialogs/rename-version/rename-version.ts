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
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';

import type { ApiError } from '@core/http/api.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NAME_MAX, NOTES_MAX, type RenameDialogData, type VersionChange } from '../../data/versions.types';
import { VersionsStore } from '../../state/versions.store';

@Component({
  selector: 'app-rename-version',
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
    MatIcon,
    MatInput,
    MatLabel,
    TranslatePipe,
  ],
  templateUrl: './rename-version.html',
  styleUrl: './rename-version.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RenameVersionDialog {
  private readonly store = inject(VersionsStore);
  private readonly reference = inject<MatDialogRef<RenameVersionDialog, boolean>>(MatDialogRef);

  readonly data = inject<RenameDialogData>(MAT_DIALOG_DATA);

  readonly nameMax = NAME_MAX;
  readonly notesMax = NOTES_MAX;

  readonly name = signal(this.data.version.name);
  readonly notes = signal(this.data.version.notes);
  readonly submitted = signal(false);
  readonly busy = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };

  async submit(): Promise<void> {
    this.submitted.set(true);
    if (this.nameInvalid()) {
      return;
    }
    const { version } = this.data;
    const name = this.name().trim();
    const notes = this.notes().trim();
    const change: VersionChange = {
      ...(name !== version.name ? { name } : {}),
      ...(notes !== version.notes ? { notes } : {}),
    };
    if (Object.keys(change).length === 0) {
      this.reference.close(false);
      return;
    }
    this.busy.set(true);
    const failure = await this.store.rename(version, change);
    this.busy.set(false);
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }
}
