import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { Term } from './term';

describe('Term', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.inject(LocaleStore).setLocale('en');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('shows the word and opens its explanation on demand', async () => {
    const fixture = TestBed.createComponent(Term);
    fixture.componentRef.setInput('key', 'vram');
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    expect(host.querySelector('.term__word')?.textContent.trim()).toBe('VRAM');
    const button = host.querySelector<HTMLButtonElement>('button');
    expect(button?.getAttribute('aria-label')).toBe('Explain: VRAM');
    expect(button?.getAttribute('aria-expanded')).toBe('false');

    button?.click();
    await fixture.whenStable();

    expect(button?.getAttribute('aria-expanded')).toBe('true');
    expect(document.querySelector('.term__panel')?.textContent).toContain('memory on the GPU');
  });
});
