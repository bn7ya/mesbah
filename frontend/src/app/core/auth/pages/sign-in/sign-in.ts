import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatDivider } from '@angular/material/divider';
import { MatError, MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { ActivatedRoute, Router } from '@angular/router';

import { LocaleSwitcher } from '@core/i18n/locale-switcher/locale-switcher';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { AuthStore } from '../../state/auth.store';

@Component({
  selector: 'app-sign-in',
  imports: [
    FormsModule,
    MatButton,
    MatCard,
    MatDivider,
    MatError,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatSuffix,
    TranslatePipe,
    LocaleSwitcher,
  ],
  templateUrl: './sign-in.html',
  styleUrl: './sign-in.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SignInPage {
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly locale = inject(LocaleStore);

  readonly username = signal('');
  readonly password = signal('');
  readonly submitted = signal(false);

  readonly revealed = signal(false);

  readonly busy = this.auth.busy;
  readonly error = this.auth.error;

  readonly usernameInvalid = computed(() => this.submitted() && this.username().trim() === '');
  readonly passwordInvalid = computed(() => this.submitted() && this.password() === '');
  readonly canSubmit = computed(() => !this.busy());

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

    if (this.usernameInvalid() || this.passwordInvalid()) {
      return;
    }

    const signedIn = await this.auth.signIn({
      username: this.username().trim(),
      password: this.password(),
    });

    if (signedIn) {
      const next = this.route.snapshot.queryParamMap.get('next') ?? '/';
      await this.router.navigateByUrl(next);
    }
  }
}
