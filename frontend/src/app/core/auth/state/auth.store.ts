import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import type { ApiError } from '@core/http/api.types';
import { AuthApi } from '../data/auth.api';
import type { Credentials, Identity, OwnerAccount } from '../data/auth.types';

@Injectable({ providedIn: 'root' })
export class AuthStore {
  private readonly api = inject(AuthApi);
  private readonly router = inject(Router);

  private readonly identity = signal<Identity | null>(null);

  readonly resolved = signal(false);
  readonly busy = signal(false);
  readonly error = signal<ApiError | null>(null);

  readonly user = this.identity.asReadonly();
  readonly isAuthenticated = computed(() => this.identity() !== null);
  readonly groups = computed<readonly string[]>(() => this.identity()?.groups ?? []);
  readonly displayName = computed(() => {
    const user = this.identity();
    if (!user) {
      return '';
    }
    const full = [user.first_name, user.last_name].filter(Boolean).join(' ');
    return full || user.username;
  });

  async restore(): Promise<void> {
    try {
      this.identity.set(await firstValueFrom(this.api.me()));
    } catch {
      this.identity.set(null);
    } finally {
      this.resolved.set(true);
    }
  }

  async signIn(credentials: Credentials): Promise<boolean> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await firstValueFrom(this.api.primeCsrf());
      this.identity.set(await firstValueFrom(this.api.signIn(credentials)));
      return true;
    } catch (error) {
      this.error.set(error as ApiError);
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  async setupNeeded(): Promise<boolean> {
    try {
      return (await firstValueFrom(this.api.setupStatus())).needed;
    } catch {
      return false;
    }
  }

  async setUp(owner: OwnerAccount): Promise<boolean> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await firstValueFrom(this.api.primeCsrf());
      this.identity.set(await firstValueFrom(this.api.setUp(owner)));
      this.resolved.set(true);
      return true;
    } catch (error) {
      this.error.set(error as ApiError);
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  forget(): void {
    this.identity.set(null);
  }

  async signOut(): Promise<void> {
    this.busy.set(true);
    try {
      await firstValueFrom(this.api.signOut());
    } catch {
      // The session is discarded either way; a failed call must not strand the user.
    } finally {
      this.identity.set(null);
      this.busy.set(false);
      await this.router.navigate(['/sign-in']);
    }
  }

  hasGroup(name: string): boolean {
    const user = this.identity();
    if (!user) {
      return false;
    }
    return user.is_superuser || user.groups.includes(name);
  }

  hasAnyGroup(names: readonly string[]): boolean {
    return names.some((name) => this.hasGroup(name));
  }

  hasPermission(codename: string): boolean {
    const user = this.identity();
    if (!user) {
      return false;
    }
    return user.is_superuser || user.permissions.includes(codename);
  }
}
