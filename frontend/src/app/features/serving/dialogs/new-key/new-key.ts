import { ChangeDetectionStrategy, Component, ElementRef, computed, effect, inject, signal, viewChild } from '@angular/core';
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

import type { ApiError } from '@core/http/api.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CopyButton } from '../../components/copy-button/copy-button';
import { NAME_MAX, type CreatedApiKey } from '../../data/serving.types';
import { ServingStore } from '../../state/serving.store';

@Component({
  selector: 'app-new-key',
  imports: [
    CopyButton,
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
  templateUrl: './new-key.html',
  styleUrl: './new-key.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewKeyDialog {
  private readonly store = inject(ServingStore);
  private readonly reference = inject<MatDialogRef<NewKeyDialog, boolean>>(MatDialogRef);

  private readonly keyField = viewChild<ElementRef<HTMLInputElement>>('keyField');

  readonly nameMax = NAME_MAX;

  readonly name = signal('');
  readonly submitted = signal(false);
  readonly failure = signal<ApiError | null>(null);
  readonly created = signal<CreatedApiKey | null>(null);

  readonly busy = this.store.creatingKey;

  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };

  constructor() {
    effect(() => {
      this.keyField()?.nativeElement.focus();
    });
  }

  async submit(): Promise<void> {
    this.submitted.set(true);
    if (this.nameInvalid()) {
      return;
    }
    const result = await this.store.createKey(this.name().trim());
    if ('key' in result) {
      this.reference.disableClose = true;
      this.created.set(result.key);
    } else {
      this.failure.set(result.error);
    }
  }

  selectAll(event: FocusEvent): void {
    (event.target as HTMLInputElement).select();
  }
}
