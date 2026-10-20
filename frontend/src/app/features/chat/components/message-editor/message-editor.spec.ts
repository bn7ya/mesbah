import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { MessageEditor } from './message-editor';

describe('MessageEditor', () => {
  let fixture: ComponentFixture<MessageEditor>;
  const saved = vi.fn<(text: string) => void>();
  const cancelled = vi.fn<() => void>();

  function host(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function field(): HTMLTextAreaElement {
    const element = host().querySelector('textarea');
    if (element === null) {
      throw new Error('no field');
    }
    return element;
  }

  async function type(text: string): Promise<void> {
    field().value = text;
    field().dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function key(key: string, init: KeyboardEventInit = {}): Promise<void> {
    field().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...init }));
    await fixture.whenStable();
  }

  async function open(inputs: Readonly<Record<string, unknown>> = {}): Promise<void> {
    fixture = TestBed.createComponent(MessageEditor);
    fixture.componentRef.setInput('initial', 'The model wrote this.');
    fixture.componentRef.setInput('labelKey', 'chat.edit.replyLabel');
    for (const [name, value] of Object.entries(inputs)) {
      fixture.componentRef.setInput(name, value);
    }
    fixture.componentInstance.saved.subscribe(saved);
    fixture.componentInstance.cancelled.subscribe(cancelled);
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    saved.mockReset();
    cancelled.mockReset();
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('opens with the current text', async () => {
    await open();

    expect(field().value).toBe('The model wrote this.');
  });

  it('saves the edited text from the Save button', async () => {
    await open();
    await type('It ships tomorrow.');

    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();

    expect(saved).toHaveBeenCalledWith('It ships tomorrow.');
  });

  it('saves with Ctrl and Enter, and with Command and Enter', async () => {
    await open();
    await type('One');

    await key('Enter', { ctrlKey: true });
    await key('Enter', { metaKey: true });

    expect(saved).toHaveBeenCalledTimes(2);
    expect(saved).toHaveBeenCalledWith('One');
  });

  it('cancels with Escape, wherever focus is inside the editor', async () => {
    await open();

    await key('Escape');
    host().querySelector('button[type=button]')?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await fixture.whenStable();

    expect(cancelled).toHaveBeenCalledTimes(2);
  });

  it('cancels from the Cancel button', async () => {
    await open();

    const buttons = host().querySelectorAll<HTMLButtonElement>('.editor__actions button');
    buttons[1].click();

    expect(cancelled).toHaveBeenCalled();
    expect(saved).not.toHaveBeenCalled();
  });

  it('does not save a reply with no text, and says why', async () => {
    await open({ requireText: true });
    await type('   ');

    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();

    expect(saved).not.toHaveBeenCalled();
    expect(host().querySelector('mat-error')?.textContent).toContain('A reply needs some text.');
  });

  it('saves empty text when the thinking may be left empty', async () => {
    await open({ initial: 'Some thinking.' });
    await type('');

    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();

    expect(saved).toHaveBeenCalledWith('');
  });

  it('offers what the model wrote only when it was edited, and shows it on request', async () => {
    await open();
    expect(host().textContent).not.toContain('Show what the model wrote');

    fixture.componentRef.setInput('original', 'First draft by the model.');
    await fixture.whenStable();
    const link = host().querySelector<HTMLButtonElement>('button[aria-expanded]');
    expect(link?.textContent.trim()).toBe('Show what the model wrote');
    expect(host().querySelector('.editor__original')).toBeNull();

    link?.click();
    await fixture.whenStable();

    expect(link?.getAttribute('aria-expanded')).toBe('true');
    expect(host().querySelector('.editor__original')?.textContent).toContain('First draft by the model.');
  });

  it('says so when the model wrote no thinking to show', async () => {
    await open({ original: '' });

    host().querySelector<HTMLButtonElement>('button[aria-expanded]')?.click();
    await fixture.whenStable();

    expect(host().querySelector('.editor__original')?.textContent).toContain('The model wrote no thinking.');
  });

  it('does not save while a save is in flight', async () => {
    await open({ busy: true });

    const submit = host().querySelector<HTMLButtonElement>('button[type=submit]');
    expect(submit?.disabled).toBe(true);
    expect(submit?.textContent.trim()).toBe('Saving…');
    await key('Enter', { ctrlKey: true });

    expect(saved).not.toHaveBeenCalled();
  });
});
