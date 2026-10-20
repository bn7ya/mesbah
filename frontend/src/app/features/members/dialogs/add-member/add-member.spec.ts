import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { MatDialogRef } from '@angular/material/dialog';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import type { NewMember } from '../../data/members.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { MembersStore } from '../../state/members.store';
import { AddMemberDialog } from './add-member';

describe('AddMemberDialog', () => {
  const add = vi.fn<(member: NewMember) => Promise<ApiError | null>>();
  const close = vi.fn<(added: boolean) => void>();

  let fixture: ComponentFixture<AddMemberDialog>;
  let host: HTMLElement;

  const field = (name: string): HTMLInputElement => host.querySelector<HTMLInputElement>(`input[name="${name}"]`)!;
  const errors = (): string[] => Array.from(host.querySelectorAll('mat-error')).map((error) => error.textContent.trim());

  async function type(name: string, value: string): Promise<void> {
    field(name).value = value;
    field(name).dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function submit(): Promise<void> {
    host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await fixture.whenStable();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    localStorage.clear();
    add.mockReset().mockResolvedValue(null);
    close.mockReset();
    TestBed.configureTestingModule({
      providers: [
        { provide: MembersStore, useValue: { busy: signal(false), add } },
        { provide: MatDialogRef, useValue: { close } },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(AddMemberDialog);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
    await type('username', 'noor');
    await type('password', 'a long hard password');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('refuses a bad email in the dialog, with a message on the field, and sends nothing', async () => {
    await type('email', 'noor-at-example');

    await submit();

    expect(errors()).toEqual(['Enter a valid email address.']);
    expect(field('email').getAttribute('aria-invalid')).toBe('true');
    expect(add).not.toHaveBeenCalled();
  });

  it('shows the same refusal in Arabic', async () => {
    TestBed.inject(LocaleStore).setLocale('ar');
    await type('email', 'noor@');

    await submit();

    expect(errors()).toEqual(['أدخل عنوان بريد إلكتروني صحيحا.']);
  });

  it('takes an email that is a real address, or none at all', async () => {
    await type('email', ' noor@example.com ');
    await submit();

    expect(errors()).toEqual([]);
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ username: 'noor', email: 'noor@example.com' }));
    expect(close).toHaveBeenCalledWith(true);

    add.mockClear();
    await type('email', '');
    await submit();

    expect(add).toHaveBeenCalledWith(expect.objectContaining({ email: '' }));
  });

  it('refuses a username with a space, and tells a missing one apart', async () => {
    await type('username', 'noor khan');
    await submit();
    expect(errors()).toEqual(['Use letters and digits, with no spaces.']);

    await type('username', '');
    expect(errors()).toEqual(['Enter a username.']);
    expect(add).not.toHaveBeenCalled();
  });

  it('accepts an Arabic username', async () => {
    await type('username', 'نور');
    await submit();

    expect(add).toHaveBeenCalledWith(expect.objectContaining({ username: 'نور' }));
  });
});
