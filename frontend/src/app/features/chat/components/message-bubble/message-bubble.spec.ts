import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { UiModeStore } from '@core/ui/ui-mode.store';
import type { VersionLabel } from '@shared/version/version.types';
import type { Message, MessageChange, StreamState } from '../../data/chat.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ConversationStore } from '../../state/conversation.store';
import { MessageBubble } from './message-bubble';

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: 'r1',
    position: 1,
    role: 'assistant',
    status: 'complete',
    content: 'It ships tomorrow.',
    thinking: '',
    version: { id: 'v0', name: 'base' },
    engine_name: 'Mesbah',
    finish_reason: 'stop',
    error_code: '',
    tokens_prompt: 12,
    tokens_completion: 20,
    latency_ms: 1500,
    original_content: null,
    original_thinking: null,
    content_edited_at: null,
    thinking_edited_at: null,
    edited_by: null,
    approved: false,
    approved_by: null,
    include_in_training: true,
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T10:00:00Z',
    ...overrides,
  };
}

describe('MessageBubble', () => {
  const stream = signal<StreamState | null>(null);
  const working = signal<readonly string[]>([]);
  const canWrite = signal(true);
  const edit = vi.fn<(target: Message, change: MessageChange) => Promise<ApiError | null>>();
  const approve = vi.fn<(target: Message, approved: boolean) => Promise<ApiError | null>>();
  const label: VersionLabel = { id: 'v0', number: 0, name: 'base' };

  let fixture: ComponentFixture<MessageBubble>;

  function host(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function text(): string {
    return host().textContent.replace(/\s+/g, ' ');
  }

  async function show(item: Message): Promise<void> {
    fixture = TestBed.createComponent(MessageBubble);
    fixture.componentRef.setInput('message', item);
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    stream.set(null);
    working.set([]);
    canWrite.set(true);
    edit.mockReset().mockResolvedValue(null);
    approve.mockReset().mockResolvedValue(null);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: ConversationStore, useValue: { stream, working, canWrite, versionLabel: () => label, edit, approve } },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
  });

  afterEach(() => {
    document.body.querySelectorAll('.cdk-overlay-container').forEach((container) => (container.innerHTML = ''));
    TestBed.resetTestingModule();
  });

  it('sets the reader\'s own message apart, with only its text and time', async () => {
    await show(message({ id: 'u1', role: 'user', content: 'Where is my order?', version: null }));

    expect(host().querySelector('.bubble--user')).not.toBeNull();
    expect(text()).toContain('Where is my order?');
    expect(host().querySelector('footer button')).toBeNull();
    expect(host().querySelector('.bubble__status')).toBeNull();
  });

  it('writes each text in its own direction and keeps its line breaks', async () => {
    await show(message({ content: 'مرحبا\nبك' }));

    const paragraph = host().querySelector('.bubble__text');
    expect(paragraph?.getAttribute('dir')).toBe('auto');
    expect(paragraph?.textContent).toBe('مرحبا\nبك');
  });

  it('names the version that answered, in words for the base', async () => {
    await show(message());

    expect(text()).toContain('v0');
    expect(text()).toContain('Base model');
  });

  it('shows a mark in words for each thing a person did to the reply', async () => {
    await show(
      message({
        approved: true,
        content_edited_at: '2026-10-18T10:05:00Z',
        thinking_edited_at: '2026-10-18T10:06:00Z',
        thinking: 'Check the date.',
        include_in_training: false,
      }),
    );

    expect(text()).toContain('Approved');
    expect(text()).toContain('Edited');
    expect(text()).toContain('Thinking edited');
    expect(text()).toContain('Not used for training');
  });

  it('says a reply was stopped', async () => {
    await show(message({ status: 'stopped' }));

    expect(text()).toContain('Stopped');
  });

  it('says why a reply failed, with the way to the engines when the engine is not running', async () => {
    await show(message({ status: 'failed', content: '', error_code: 'engine_unreachable' }));

    expect(host().querySelector('.bubble__failure')?.textContent).toContain('The engine isn\'t running.');
    expect(host().querySelector('a')?.getAttribute('href')).toBe('/engines');
    expect(text()).toContain('Failed');
  });

  it('falls back to a plain sentence for a failure it has no words for', async () => {
    await show(message({ status: 'failed', content: '', error_code: 'something_new' }));

    expect(host().querySelector('.bubble__failure')?.textContent).toContain("The reply couldn't be completed.");
    expect(host().querySelector('a')).toBeNull();
  });

  it('shows the text that is arriving, in a live region that says what is happening', async () => {
    await show(message({ status: 'streaming', content: '', engine_name: '' }));
    stream.set({ replyId: 'r1', phase: 'loading', thinking: '', content: '', engine: '' });
    await fixture.whenStable();
    const region = host().querySelector('.bubble__status');
    expect(region?.getAttribute('aria-live')).toBe('polite');
    expect(region?.textContent).toContain('Loading the model…');

    stream.set({ replyId: 'r1', phase: 'thinking', thinking: 'Let me check.', content: '', engine: 'Mesbah' });
    await fixture.whenStable();
    expect(region?.textContent).toContain('Thinking…');
    expect(host().querySelector('.bubble__thinking')?.textContent).toBe('Let me check.');

    stream.set({ replyId: 'r1', phase: 'writing', thinking: 'Let me check.', content: 'It ships', engine: 'Mesbah' });
    await fixture.whenStable();
    expect(region?.textContent).toContain('Writing…');
    expect(host().querySelector('.bubble__text')?.textContent).toBe('It ships');
    expect(host().querySelector('footer button')).toBeNull();
  });

  it('ignores a stream that belongs to another reply', async () => {
    await show(message());
    stream.set({ replyId: 'other', phase: 'writing', thinking: '', content: 'Not mine', engine: '' });
    await fixture.whenStable();

    expect(host().querySelector('.bubble__text')?.textContent).toBe('It ships tomorrow.');
    expect(host().querySelector('.bubble__progress')).toBeNull();
  });

  it('gives a reviewer a menu, and a viewer only Copy', async () => {
    await show(message());
    expect(host().querySelector('button[aria-label="Reply actions"]')).not.toBeNull();

    canWrite.set(false);
    await fixture.whenStable();

    expect(host().querySelector('button[aria-label="Reply actions"]')).toBeNull();
    expect(host().querySelector('button[aria-label="Copy"]')).not.toBeNull();
  });

  it('shows the details of a reply to an expert', async () => {
    TestBed.inject(UiModeStore).setMode('expert');
    await show(message({ edited_by: 'rana', approved: true, approved_by: 'rana' }));

    expect(text()).toContain('Mesbah');
    expect(text()).toContain('Prompt: 12. Reply: 20.');
    expect(text()).toContain('1.5 s');
    expect(text()).toContain('Approved by');
  });

  it('keeps those details from a simple reader', async () => {
    await show(message());

    expect(text()).not.toContain('in the prompt');
  });

  it('turns the reply into an editor, saves only the reply, and puts the bubble back', async () => {
    await show(message());

    fixture.componentInstance.startEdit('content');
    await fixture.whenStable();
    const field = host().querySelector<HTMLTextAreaElement>('textarea');
    expect(field?.value).toBe('It ships tomorrow.');
    expect(host().querySelector('footer')).toBeNull();

    if (field === null) {
      throw new Error('no editor');
    }
    field.value = 'It ships today.';
    field.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();
    await fixture.whenStable();

    expect(edit).toHaveBeenCalledWith(expect.objectContaining({ id: 'r1' }), { content: 'It ships today.' });
    expect(host().querySelector('textarea')).toBeNull();
    expect(host().querySelector('footer')).not.toBeNull();
  });

  it('closes the editor without a request when nothing changed', async () => {
    await show(message());
    fixture.componentInstance.startEdit('content');
    await fixture.whenStable();

    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();
    await fixture.whenStable();

    expect(edit).not.toHaveBeenCalled();
    expect(host().querySelector('textarea')).toBeNull();
  });

  it('keeps the editor open, with the text, when the save is refused', async () => {
    edit.mockResolvedValue({ code: 'message_changed', message: 'Someone else changed this reply.' });
    await show(message());
    fixture.componentInstance.startEdit('content');
    await fixture.whenStable();
    const field = host().querySelector<HTMLTextAreaElement>('textarea');
    if (field === null) {
      throw new Error('no editor');
    }
    field.value = 'Mine';
    field.dispatchEvent(new Event('input'));
    await fixture.whenStable();

    host().querySelector<HTMLButtonElement>('button[type=submit]')?.click();
    await fixture.whenStable();
    await fixture.whenStable();

    expect(host().querySelector<HTMLTextAreaElement>('textarea')?.value).toBe('Mine');
  });

  it('edits the thinking on its own, and opens its section to do it', async () => {
    await show(message());

    fixture.componentInstance.startEdit('thinking');
    await fixture.whenStable();

    expect(host().querySelector('app-thinking-section')).not.toBeNull();
    expect(host().querySelector('textarea')).not.toBeNull();
    expect(host().querySelector('app-thinking-section button[aria-expanded]')?.getAttribute('aria-expanded')).toBe('true');
    expect(host().querySelector('.bubble__text')?.textContent).toBe('It ships tomorrow.');
  });

  it('approves a reply as it is, and takes the approval back', async () => {
    await show(message());
    await fixture.componentInstance.toggleApproved();
    expect(approve).toHaveBeenLastCalledWith(expect.objectContaining({ id: 'r1' }), true);

    await show(message({ approved: true }));
    await fixture.componentInstance.toggleApproved();
    expect(approve).toHaveBeenLastCalledWith(expect.objectContaining({ id: 'r1' }), false);
  });

  describe('a reply with nothing written', () => {
    async function menuItems(): Promise<string[]> {
      host().querySelector<HTMLButtonElement>('button[aria-label="Reply actions"]')?.click();
      await fixture.whenStable();
      return Array.from(document.querySelectorAll('.mat-mdc-menu-panel [role^="menuitem"]')).map((item) =>
        item.textContent.trim(),
      );
    }

    it('shows a reply stopped while the model was loading as stopped with nothing written', async () => {
      await show(message({ status: 'stopped', content: '', thinking: '', engine_name: '' }));

      expect(host().querySelector('.bubble__empty')?.textContent).toContain('Stopped before the model wrote anything.');
      expect(text()).toContain('Stopped');
      expect(text()).not.toContain('Not used for training');
    });

    it('offers neither approval nor use for training', async () => {
      await show(message({ status: 'stopped', content: '  ', thinking: '' }));

      const items = await menuItems();

      expect(items).toContain('Edit reply');
      expect(items.some((item) => item.includes('Approve'))).toBe(false);
      expect(items.some((item) => item.includes('Used for training'))).toBe(false);
    });

    it('still lets a person withdraw an approval it already has', async () => {
      await show(message({ status: 'stopped', content: '', approved: true }));

      const items = await menuItems();

      expect(items.some((item) => item.includes('Withdraw approval'))).toBe(true);
    });

    it('says the model wrote nothing when a finished reply is empty', async () => {
      await show(message({ status: 'complete', content: '', thinking: '' }));

      expect(host().querySelector('.bubble__empty')?.textContent).toContain('The model wrote nothing.');
    });

    it('is not empty when only the thinking was written', async () => {
      await show(message({ status: 'stopped', content: '', thinking: 'Let me check.' }));

      expect(host().querySelector('.bubble__empty')).toBeNull();
      expect((await menuItems()).some((item) => item.includes('Approve'))).toBe(true);
    });

    it('leaves a failed reply to its own reason', async () => {
      await show(message({ status: 'failed', content: '', error_code: 'engine_failed' }));

      expect(host().querySelector('.bubble__empty')).toBeNull();
      expect(host().querySelector('.bubble__failure')).not.toBeNull();
    });
  });

  it('switches use for training with the reply\'s own flag', async () => {
    await show(message({ include_in_training: true }));

    await fixture.componentInstance.toggleTraining();

    expect(edit).toHaveBeenCalledWith(expect.objectContaining({ id: 'r1' }), { include_in_training: false });
  });
});
