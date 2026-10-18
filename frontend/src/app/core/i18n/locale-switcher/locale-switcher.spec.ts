import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '../locale.store';
import { LocaleSwitcher } from './locale-switcher';

describe('LocaleSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('offers both languages as one exclusive choice, the current one checked', async () => {
    TestBed.inject(LocaleStore).setLocale('en');
    const fixture = TestBed.createComponent(LocaleSwitcher);
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    expect(host.querySelector('[role="radiogroup"]')?.getAttribute('aria-label')).toBe('Language');
    const options = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="radio"]'));
    expect(options.map((option) => option.textContent.trim())).toEqual(['English', 'العربية']);
    expect(options.map((option) => option.getAttribute('aria-checked'))).toEqual(['true', 'false']);
  });

  it('switches the language when the other option is chosen', async () => {
    const locale = TestBed.inject(LocaleStore);
    locale.setLocale('en');
    const fixture = TestBed.createComponent(LocaleSwitcher);
    await fixture.whenStable();

    (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>('[role="radio"]')[1].click();
    await fixture.whenStable();

    expect(locale.locale()).toBe('ar');
  });
});
