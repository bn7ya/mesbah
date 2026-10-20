import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatDialogActions, MatDialogClose, MatDialogContent, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';

import { ROLE_LADDER, type Role } from '@core/auth/roles.types';
import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import { MembersStore } from '../../state/members.store';

const USERNAME = /^[\p{L}\p{N}_.@+-]+$/u;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

@Component({
  selector: 'app-add-member',
  imports: [
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
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSuffix,
    Note,
    TranslatePipe,
  ],
  templateUrl: './add-member.html',
  styleUrl: './add-member.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AddMemberDialog {
  private readonly store = inject(MembersStore);
  private readonly locale = inject(LocaleStore);
  private readonly reference = inject<MatDialogRef<AddMemberDialog, boolean>>(MatDialogRef);

  readonly roles = ROLE_LADDER;

  readonly username = signal('');
  readonly password = signal('');
  readonly role = signal<Role>('reviewers');
  readonly firstName = signal('');
  readonly lastName = signal('');
  readonly email = signal('');
  readonly revealed = signal(false);
  readonly submitted = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly busy = this.store.busy;

  readonly usernameMissing = computed(() => this.username().trim() === '');
  readonly usernameInvalid = computed(
    () => this.submitted() && (this.usernameMissing() || !USERNAME.test(this.username().trim())),
  );
  readonly passwordInvalid = computed(() => this.submitted() && this.password() === '');
  readonly emailInvalid = computed(() => {
    const email = this.email().trim();
    return this.submitted() && email !== '' && !EMAIL.test(email);
  });
  readonly usernameErrors: ErrorStateMatcher = { isErrorState: () => this.usernameInvalid() };
  readonly passwordErrors: ErrorStateMatcher = { isErrorState: () => this.passwordInvalid() };
  readonly emailErrors: ErrorStateMatcher = { isErrorState: () => this.emailInvalid() };

  readonly revealLabel = computed(() =>
    this.locale.translate(this.revealed() ? 'auth.signIn.hidePassword' : 'auth.signIn.showPassword'),
  );

  toggleReveal(): void {
    this.revealed.update((revealed) => !revealed);
  }

  async submit(): Promise<void> {
    this.submitted.set(true);
    if (this.usernameInvalid() || this.passwordInvalid() || this.emailInvalid()) {
      return;
    }
    const failure = await this.store.add({
      username: this.username().trim(),
      password: this.password(),
      role: this.role(),
      first_name: this.firstName().trim(),
      last_name: this.lastName().trim(),
      email: this.email().trim(),
    });
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }
}
