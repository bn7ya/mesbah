import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ConversationStore } from '../../state/conversation.store';
import { Composer } from './composer';

describe('Composer', () => {
  const canWrite = signal(true);
  const ready = signal(true);
  const sending = signal(false);
  const sendError = signal<ApiError | null>(null);
  const send = vi.fn<(content: string) => Promise<boolean>>();
  const stop = vi.fn<() => Promise<void>>();

  let fixture: ComponentFixture<Composer>;

  function host(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function field(): HTMLTextAreaElement {
    const element = host().querySelector('textarea');
    if (element === null) {
      throw new Error('no message field');
    }
    return element;
  }

  async function type(text: string): Promise<void> {
    field().value = text;
    field().dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function press(key: string, init: KeyboardEventInit = {}): Promise<KeyboardEvent> {
    const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init });
    field().dispatchEvent(event);
    await fixture.whenStable();
    return event;
  }

  beforeEach(async () => {
    localStorage.clear();
    canWrite.set(true);
    ready.set(true);
    sending.set(false);
    sendError.set(null);
    send.mockReset().mockResolvedValue(true);
    stop.mockReset().mockResolvedValue(undefined);
    TestBed.configureTestingModule({
      providers: [{ provide: ConversationStore, useValue: { canWrite, ready, sending, sendError, send, stop } }],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(Composer);
    await fixture.whenStable();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('sends what was typed when Enter is pressed, and empties the field', async () => {
    await type('Where is my order?');

    const event = await press('Enter');

    expect(send).toHaveBeenCalledWith('Where is my order?');
    expect(event.defaultPrevented).toBe(true);
    expect(field().value).toBe('');
  });

  it('adds a line instead of sending when Shift and Enter are pressed', async () => {
    await type('One');

    const event = await press('Enter', { shiftKey: true });

    expect(send).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it('does not send while an input method is still composing', async () => {
    await type('مرحبا');

    await press('Enter', { isComposing: true });

    expect(send).not.toHaveBeenCalled();
  });

  it('does not send blank text', async () => {
    await type('   ');

    await press('Enter');

    expect(send).not.toHaveBeenCalled();
    expect(host().querySelector<HTMLButtonElement>('button[type=submit]')?.disabled).toBe(true);
  });

  it('sends from the Send button', async () => {
    await type('Hi');

    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();

    expect(send).toHaveBeenCalledWith('Hi');
  });

  it('puts the text back when the message could not be sent', async () => {
    send.mockResolvedValue(false);
    await type('Try again');

    await press('Enter');
    await fixture.whenStable();

    expect(field().value).toBe('Try again');
  });

  it('shows why a message could not be sent', async () => {
    sendError.set({ code: 'no_version', message: 'This project has no version to chat with.' });
    await fixture.whenStable();

    expect(host().querySelector('[role=alert]')?.textContent).toContain('no version');
  });

  it('turns Send into Stop while a reply streams, and stops it', async () => {
    sending.set(true);
    await fixture.whenStable();

    const button = host().querySelector<HTMLButtonElement>('button.composer__action');
    expect(button?.textContent.trim()).toBe('Stop');
    expect(button?.type).toBe('button');

    button?.click();

    expect(stop).toHaveBeenCalled();
  });

  it('waits for the conversation before it takes text', async () => {
    ready.set(false);
    await fixture.whenStable();

    expect(field().disabled).toBe(true);
  });

  it('shows a viewer that the conversation is for reading, with no field', async () => {
    canWrite.set(false);
    await fixture.whenStable();

    expect(host().querySelector('textarea')).toBeNull();
    expect(host().textContent).toContain('Reading only');
  });
});
