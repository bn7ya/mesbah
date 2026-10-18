import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { Money, RIAL_SIGN } from './money';

describe('Money', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('shows the amount to the baisa beside the Omani rial sign', async () => {
    TestBed.inject(LocaleStore).setLocale('en');
    const fixture = TestBed.createComponent(Money);
    fixture.componentRef.setInput('amount', '1234.5');
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    expect(RIAL_SIGN).toBe('⃄');
    expect(host.querySelector('.money__sign')?.textContent).toBe(RIAL_SIGN);
    expect(host.querySelector('.money__amount')?.textContent).toBe('1,234.500');
    expect(host.textContent).not.toMatch(/OMR|O\.R|R\.O|ر\.ع/);
  });

  it('keeps Latin digits in Arabic', async () => {
    TestBed.inject(LocaleStore).setLocale('ar');
    const fixture = TestBed.createComponent(Money);
    fixture.componentRef.setInput('amount', 7);
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).querySelector('.money__amount')?.textContent).toBe('7.000');
  });
});
