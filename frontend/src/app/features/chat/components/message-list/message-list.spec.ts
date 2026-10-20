import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import type { Message } from '../../data/chat.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ConversationStore } from '../../state/conversation.store';
import { MessageList } from './message-list';

describe('MessageList', () => {
  const conversationId = signal<string | null>('c1');
  const sending = signal(false);

  let fixture: ComponentFixture<MessageList>;
  let box: { height: number; top: number };

  function scroller(): HTMLElement {
    return fixture.componentInstance.scroller().nativeElement;
  }

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        {
          provide: ConversationStore,
          useValue: {
            conversationId,
            sending,
            messages: signal<readonly Message[]>([]),
            loading: signal(false),
            ready: signal(true),
          },
        },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(MessageList);
    await fixture.whenStable();

    box = { height: 1000, top: 600 };
    const element = scroller();
    Object.defineProperty(element, 'clientHeight', { configurable: true, get: () => 400 });
    Object.defineProperty(element, 'scrollHeight', { configurable: true, get: () => box.height });
    Object.defineProperty(element, 'scrollTop', {
      configurable: true,
      get: () => box.top,
      set: (value: number) => (box.top = Math.min(value, box.height - 400)),
    });
    fixture.componentInstance.changed();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('follows the list to the bottom when it grows', () => {
    box.top = 580;
    box.height = 1200;

    fixture.componentInstance.changed();

    expect(box.top).toBe(800);
  });

  it('stays where the reader is when the DOM changes without the list growing', () => {
    box.top = 570;
    fixture.componentInstance.scrolled();

    fixture.componentInstance.changed();

    expect(box.top).toBe(570);
  });

  it('stops following once the reader has scrolled well up', () => {
    box.top = 200;
    fixture.componentInstance.scrolled();
    box.height = 1200;

    fixture.componentInstance.changed();

    expect(box.top).toBe(200);
    expect(fixture.componentInstance.pinned()).toBe(false);
  });
});
