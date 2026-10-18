import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { UiModeStore } from '../ui-mode.store';
import { UiModeSwitcher } from './ui-mode-switcher';

describe('UiModeSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('starts in Simple mode', () => {
    expect(TestBed.inject(UiModeStore).mode()).toBe('simple');
  });

  it('switches to Expert mode and remembers it', async () => {
    TestBed.inject(LocaleStore).setLocale('en');
    const store = TestBed.inject(UiModeStore);
    const fixture = TestBed.createComponent(UiModeSwitcher);
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    const options = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="radio"]'));
    expect(options.map((option) => option.textContent.trim())).toEqual(['Simple', 'Expert']);

    options[1].click();
    await fixture.whenStable();

    expect(store.expert()).toBe(true);
    expect(localStorage.getItem('ui-mode')).toBe('expert');
  });
});
