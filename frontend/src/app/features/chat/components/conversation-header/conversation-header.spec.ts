import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import type {
  Conversation,
  ConversationChange,
  EngineOption,
  ProjectDefaults,
  VersionOption,
} from '../../data/chat.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ConversationStore } from '../../state/conversation.store';
import { ConversationsStore } from '../../state/conversations.store';
import { ConversationHeader } from './conversation-header';

const CONVERSATION: Conversation = {
  id: 'c1',
  project: 'p1',
  title: 'Orders',
  version: null,
  engine: null,
  system_prompt: '',
  thinking: false,
  generation: {},
  message_count: 2,
  created_at: '2026-10-18T10:00:00Z',
  updated_at: '2026-10-18T10:00:00Z',
};

function defaults(supportsThinking: boolean): ProjectDefaults {
  return {
    system_prompt: '',
    thinking: false,
    supports_thinking: supportsThinking,
    generation: { temperature: 0.7, top_p: 0.9, max_tokens: 1024 },
  };
}

describe('ConversationHeader', () => {
  const conversation = signal<Conversation | null>(CONVERSATION);
  const canWrite = signal(true);
  const changing = signal(false);
  const project = signal<ProjectDefaults | null>(null);
  const change = vi.fn<(update: ConversationChange) => Promise<null>>();

  let fixture: ComponentFixture<ConversationHeader>;

  function host(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function thinkingSwitch(): HTMLButtonElement {
    const control = host().querySelector<HTMLButtonElement>('.head__thinking button[role="switch"]');
    if (control === null) {
      throw new Error('no Thinking switch');
    }
    return control;
  }

  async function show(supportsThinking: boolean | null): Promise<void> {
    project.set(supportsThinking === null ? null : defaults(supportsThinking));
    fixture = TestBed.createComponent(ConversationHeader);
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    conversation.set(CONVERSATION);
    canWrite.set(true);
    changing.set(false);
    change.mockReset().mockResolvedValue(null);
    TestBed.configureTestingModule({
      providers: [
        { provide: ConversationStore, useValue: { conversation, canWrite, changing, change } },
        {
          provide: ConversationsStore,
          useValue: {
            versions: signal<readonly VersionOption[]>([]),
            engines: signal<readonly EngineOption[]>([]),
            activeVersion: signal<VersionOption | null>(null),
            defaults: project,
          },
        },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('turns the Thinking switch off, and says why, for a base model that cannot think', async () => {
    await show(false);

    const reason = host().querySelector('#chat-thinking-reason');
    expect(thinkingSwitch().disabled).toBe(true);
    expect(reason?.textContent.trim()).toBe("This base model doesn't write out its thinking.");
    expect(thinkingSwitch().getAttribute('aria-describedby')).toBe('chat-thinking-reason');
  });

  it('leaves the switch on offer for a base model that can think', async () => {
    await show(true);

    expect(thinkingSwitch().disabled).toBe(false);
    expect(host().querySelector('#chat-thinking-reason')).toBeNull();

    thinkingSwitch().click();
    await fixture.whenStable();

    expect(change).toHaveBeenCalledWith({ thinking: true });
  });

  it('does not judge the model before the project has loaded', async () => {
    await show(null);

    expect(thinkingSwitch().disabled).toBe(false);
    expect(host().querySelector('#chat-thinking-reason')).toBeNull();
  });
});
