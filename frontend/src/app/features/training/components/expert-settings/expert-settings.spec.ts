import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { FALLBACK_SETTINGS } from '../../data/training.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ExpertSettings } from './expert-settings';

describe('ExpertSettings', () => {
  let fixture: ComponentFixture<ExpertSettings>;
  let host: HTMLElement;

  const hint = (name: string): string =>
    host
      .querySelector(`input[name="${name}"]`)!
      .closest('mat-form-field')!
      .querySelector('mat-hint')!
      .textContent.replace(/\s+/g, ' ')
      .trim();

  async function show(): Promise<void> {
    fixture = TestBed.createComponent(ExpertSettings);
    fixture.componentRef.setInput('settings', FALLBACK_SETTINGS);
    fixture.componentRef.setInput('defaults', FALLBACK_SETTINGS);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    TestBed.inject(LocaleStore).register({ en, ar });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('writes the default of Maximum steps as no limit, in words', async () => {
    TestBed.inject(LocaleStore).setLocale('en');
    await show();

    expect(hint('max_steps')).toContain('Default: No limit.');
    expect(hint('max_steps')).not.toContain('None');
  });

  it('writes it in Arabic as well', async () => {
    TestBed.inject(LocaleStore).setLocale('ar');
    await show();

    expect(hint('max_steps')).toContain('الافتراضي: بلا حد.');
  });

  it('keeps a number as the default of a setting that has one', async () => {
    TestBed.inject(LocaleStore).setLocale('en');
    await show();

    expect(hint('max_seq_len')).toMatch(/Default: [\d.,]+\./);
  });
});
