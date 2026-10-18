import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ThinkingSection } from './thinking-section';

describe('ThinkingSection', () => {
  let fixture: ComponentFixture<ThinkingSection>;

  function toggle(): HTMLButtonElement {
    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('button[aria-expanded]');
    if (button === null) {
      throw new Error('no toggle');
    }
    return button;
  }

  function isOpen(): boolean {
    return toggle().getAttribute('aria-expanded') === 'true';
  }

  async function set(inputs: Readonly<Record<string, boolean>>): Promise<void> {
    for (const [name, value] of Object.entries(inputs)) {
      fixture.componentRef.setInput(name, value);
    }
    await fixture.whenStable();
  }

  beforeEach(async () => {
    localStorage.clear();
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(ThinkingSection);
    await fixture.whenStable();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('is closed for a finished reply', () => {
    expect(isOpen()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).querySelector('.thinking__body')).toBeNull();
  });

  it('is open while the reply streams, and closes once it is done', async () => {
    await set({ streaming: true });
    expect(isOpen()).toBe(true);

    await set({ streaming: false });
    expect(isOpen()).toBe(false);
  });

  it('opens and closes on the reader\'s click, and says what the click will do', async () => {
    expect(toggle().getAttribute('aria-label')).toBe('Show the thinking');

    toggle().click();
    await fixture.whenStable();

    expect(isOpen()).toBe(true);
    expect(toggle().getAttribute('aria-label')).toBe('Hide the thinking');
    expect(toggle().getAttribute('aria-controls')).toBe((fixture.nativeElement as HTMLElement).querySelector('.thinking__body')?.id);
  });

  it('is open while it is edited, and stays open after the edit', async () => {
    await set({ editing: true });
    expect(isOpen()).toBe(true);

    await set({ editing: false });
    expect(isOpen()).toBe(true);
  });

  it('lets the reader close it while the reply still streams', async () => {
    await set({ streaming: true });

    toggle().click();
    await fixture.whenStable();

    expect(isOpen()).toBe(false);
  });
});
