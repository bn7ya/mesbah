import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatDivider } from '@angular/material/divider';
import { MatError, MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { Router } from '@angular/router';

import { LocaleSwitcher } from '@core/i18n/locale-switcher/locale-switcher';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import { AuthStore } from '../../state/auth.store';

@Component({
  selector: 'app-setup',
  imports: [
    FormsModule,
    LocaleSwitcher,
    MatButton,
    MatCard,
    MatDivider,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatSuffix,
    Note,
    TranslatePipe,
  ],
  templateUrl: './setup.html',
  styleUrl: './setup.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SetupPage {
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly locale = inject(LocaleStore);

  readonly code = signal('');
  readonly name = signal('');
  readonly username = signal('');
  readonly password = signal('');
  readonly revealed = signal(false);
  readonly submitted = signal(false);

  readonly busy = this.auth.busy;
  readonly error = this.auth.error;

  readonly codeInvalid = computed(() => this.submitted() && this.code().trim() === '');
  readonly usernameInvalid = computed(() => this.submitted() && this.username().trim() === '');
  readonly passwordInvalid = computed(() => this.submitted() && this.password() === '');

  readonly codeErrors: ErrorStateMatcher = { isErrorState: () => this.codeInvalid() };
  readonly usernameErrors: ErrorStateMatcher = { isErrorState: () => this.usernameInvalid() };
  readonly passwordErrors: ErrorStateMatcher = { isErrorState: () => this.passwordInvalid() };

  readonly revealLabel = computed(() =>
    this.locale.translate(this.revealed() ? 'auth.signIn.hidePassword' : 'auth.signIn.showPassword'),
  );

  toggleReveal(): void {
    this.revealed.update((revealed) => !revealed);
  }

  async submit(): Promise<void> {
    this.submitted.set(true);
    if (this.codeInvalid() || this.usernameInvalid() || this.passwordInvalid()) {
      return;
    }
    const done = await this.auth.setUp({
      code: this.code().trim(),
      username: this.username().trim(),
      password: this.password(),
      first_name: this.name().trim(),
    });
    if (done) {
      await this.router.navigateByUrl('/');
    }
  }
}
