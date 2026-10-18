import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { CodeBlock } from './code-block';

describe('CodeBlock', () => {
  let fixture: ComponentFixture<CodeBlock>;

  const body = (): HTMLElement => (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>('pre')!;

  async function show(overflow: boolean, label: string | null = null): Promise<void> {
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(overflow ? 600 : 100);
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(300);
    fixture = TestBed.createComponent(CodeBlock);
    fixture.componentRef.setInput('code', 'pip install "mesbah[train]"');
    fixture.componentRef.setInput('label', label);
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    TestBed.inject(LocaleStore).setLocale('en');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('shows the code as written, in a block that never wraps', async () => {
    await show(false);

    const style = getComputedStyle(body());
    expect(body().textContent).toBe('pip install "mesbah[train]"');
    expect(body().getAttribute('dir')).toBe('ltr');
    expect(style.whiteSpace).toBe('pre');
    expect(style.overflowX).toBe('auto');
  });

  it('is left out of the tab order while everything fits', async () => {
    await show(false);

    expect(body().hasAttribute('tabindex')).toBe(false);
    expect(body().hasAttribute('role')).toBe(false);
  });

  it('can be reached from the keyboard, with a name, once it scrolls', async () => {
    await show(true);

    expect(body().getAttribute('tabindex')).toBe('0');
    expect(body().getAttribute('role')).toBe('region');
    expect(body().getAttribute('aria-label')).toBe('Code');
  });

  it('takes its name from the label when there is one', async () => {
    await show(true, 'Install command');

    expect(body().getAttribute('aria-label')).toBe('Install command');
  });
});
