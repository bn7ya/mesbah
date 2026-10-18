import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { SignInPage } from './sign-in';

describe('SignInPage', () => {
  let fixture: ComponentFixture<SignInPage>;
  let host: HTMLElement;

  const field = (name: string): HTMLInputElement => host.querySelector<HTMLInputElement>(`input[name="${name}"]`)!;
  const errors = (): string[] =>
    Array.from(host.querySelectorAll('mat-error')).map((error) => error.textContent.trim());

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    TestBed.inject(LocaleStore).setLocale('en');
    fixture = TestBed.createComponent(SignInPage);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('labels both fields and reports nothing before the first attempt', () => {
    const labels = Array.from(host.querySelectorAll('mat-label')).map((label) => label.textContent.trim());

    expect(labels).toEqual(['Username', 'Password']);
    expect(errors()).toEqual([]);
  });

  it('reports each missing field on submit, and marks it invalid', async () => {
    host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await fixture.whenStable();

    expect(errors()).toEqual(['Enter your username.', 'Enter your password.']);
    expect(field('username').getAttribute('aria-invalid')).toBe('true');
    expect(field('password').getAttribute('aria-invalid')).toBe('true');
  });

  it('clears a field’s error once it is filled in', async () => {
    host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await fixture.whenStable();

    field('username').value = 'sara';
    field('username').dispatchEvent(new Event('input'));
    await fixture.whenStable();

    expect(errors()).toEqual(['Enter your password.']);
    expect(field('username').getAttribute('aria-invalid')).toBe('false');
  });

  it('reveals and hides the password from the button in the field', async () => {
    const toggle = host.querySelector<HTMLButtonElement>('button[aria-pressed]')!;
    expect(field('password').type).toBe('password');
    expect(toggle.getAttribute('aria-label')).toBe('Show password');

    toggle.click();
    await fixture.whenStable();

    expect(field('password').type).toBe('text');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    expect(toggle.getAttribute('aria-label')).toBe('Hide password');
  });
});
