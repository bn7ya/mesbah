import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import { SetupPage } from './setup';

const settle = (): Promise<void> => new Promise<void>((resolve) => queueMicrotask(resolve));

describe('SetupPage', () => {
  let fixture: ComponentFixture<SetupPage>;
  let host: HTMLElement;
  let backend: HttpTestingController;

  const type = (name: string, value: string): void => {
    const input = host.querySelector<HTMLInputElement>(`input[name="${name}"]`)!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };
  const submit = (): void => host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    TestBed.inject(LocaleStore).setLocale('en');
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SetupPage);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  afterEach(() => {
    backend.verify();
    TestBed.resetTestingModule();
  });

  it('asks for the code before anything else', async () => {
    submit();
    await fixture.whenStable();

    const errors = Array.from(host.querySelectorAll('mat-error')).map((error) => error.textContent.trim());
    expect(errors).toEqual(['Enter the setup code.', 'Enter your username.', 'Enter your password.']);
  });

  it('creates the owner and goes to the start page', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    type('code', 'K7QF-2M9X-PL4T');
    type('username', 'owner');
    type('password', 'correct-horse-battery-staple');
    submit();
    await settle();

    backend.expectOne('/api/auth/csrf/').flush(null);
    await settle();
    const request = backend.expectOne('/api/auth/setup/');
    expect(request.request.body).toEqual({
      code: 'K7QF-2M9X-PL4T',
      username: 'owner',
      password: 'correct-horse-battery-staple',
      first_name: '',
    });
    request.flush({
      id: 1,
      username: 'owner',
      email: '',
      first_name: '',
      last_name: '',
      is_staff: true,
      is_superuser: true,
      groups: ['admins'],
      permissions: [],
    });
    await fixture.whenStable();

    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('shows a wrong code in the reader language', async () => {
    type('code', 'nope');
    type('username', 'owner');
    type('password', 'correct-horse-battery-staple');
    submit();
    await settle();
    backend.expectOne('/api/auth/csrf/').flush(null);
    await settle();
    backend
      .expectOne('/api/auth/setup/')
      .flush({ error: { code: 'setup_code_rejected', message: 'No.' } }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();

    expect(host.querySelector('[role="alert"]')?.textContent).toContain("That setup code doesn't match.");
  });
});
