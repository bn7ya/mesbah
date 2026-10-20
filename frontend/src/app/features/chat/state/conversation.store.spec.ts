import { HttpEventType, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import { SETTLE_ATTEMPTS, SETTLE_DELAY_MS, type Conversation, type Message } from '../data/chat.types';
import { ConversationStore } from './conversation.store';
import { ConversationsStore } from './conversations.store';

function conversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'c1',
    project: 'p1',
    title: '',
    version: null,
    engine: null,
    system_prompt: '',
    thinking: false,
    generation: {},
    message_count: null,
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T10:00:00Z',
    ...overrides,
  };
}

function message(id: string, overrides: Partial<Message> = {}): Message {
  return {
    id,
    position: 0,
    role: 'assistant',
    status: 'complete',
    content: 'The model wrote this.',
    thinking: '',
    version: { id: 'v0', name: 'base' },
    engine_name: 'Mesbah',
    finish_reason: 'stop',
    error_code: '',
    tokens_prompt: 12,
    tokens_completion: 20,
    latency_ms: 900,
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

function page<T>(rows: T[], overrides: Partial<Page<T>> = {}): Page<T> {
  return { count: rows.length, next: null, previous: null, results: rows, ...overrides };
}

function frame(event: string, data: object): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

const ASKED = message('u1', { role: 'user', content: 'Where is my order?', version: null, engine_name: '' });
const PLACEHOLDER = message('r1', { status: 'streaming', content: '', engine_name: '', latency_ms: null });
const SAVED = message('r1', { content: 'It ships tomorrow.', updated_at: '2026-10-18T10:01:00Z' });

describe('ConversationStore', () => {
  let store: ConversationStore;
  let backend: HttpTestingController;
  let streamed = '';

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function open(messages: Message[] = [ASKED, SAVED]): Promise<void> {
    store.open('c1');
    await settle();
    backend.expectOne('/api/chat/c1/').flush(conversation());
    backend.expectOne((request) => request.url === '/api/chat/c1/messages/').flush(page(messages));
    await settle();
  }

  function replyRequest(): TestRequest {
    return backend.expectOne((request) => request.url === '/api/chat/c1/reply/');
  }

  function push(request: TestRequest, chunk: string): void {
    streamed += chunk;
    request.event({ type: HttpEventType.DownloadProgress, loaded: streamed.length, partialText: streamed });
  }

  async function begin(): Promise<{ request: TestRequest; sent: Promise<boolean> }> {
    const sent = store.send('Where is my order?');
    const request = replyRequest();
    push(request, frame('start', { asked: ASKED, reply: PLACEHOLDER }));
    expect(await sent).toBe(true);
    return { request, sent };
  }

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    streamed = '';
    TestBed.configureTestingModule({
      providers: [
        ConversationsStore,
        ConversationStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: () => true } },
      ],
    });
    TestBed.inject(LocaleStore).setLocale('en');
    store = TestBed.inject(ConversationStore);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    try {
      backend.verify();
    } finally {
      TestBed.resetTestingModule();
      vi.useRealTimers();
    }
  });

  describe('opening', () => {
    it('loads the conversation and its messages, oldest first', async () => {
      store.open('c1');
      await settle();
      expect(store.loading()).toBe(true);
      backend.expectOne('/api/chat/c1/').flush(conversation({ title: 'Orders' }));
      const messages = backend.expectOne((request) => request.url === '/api/chat/c1/messages/');
      expect(messages.request.params.get('page_size')).toBe('200');
      messages.flush(page([ASKED, SAVED]));
      await settle();

      expect(store.loading()).toBe(false);
      expect(store.ready()).toBe(true);
      expect(store.conversation()?.title).toBe('Orders');
      expect(store.messages().map((row) => row.id)).toEqual(['u1', 'r1']);
    });

    it('follows the pages until every message is here', async () => {
      store.open('c1');
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation());
      backend
        .expectOne((request) => request.url === '/api/chat/c1/messages/')
        .flush(page([ASKED], { count: 2, next: 'http://x/?page=2' }));
      await settle();
      const second = backend.expectOne((request) => request.url === '/api/chat/c1/messages/');
      expect(second.request.params.get('page')).toBe('2');
      second.flush(page([SAVED], { count: 2 }));
      await settle();

      expect(store.messages().map((row) => row.id)).toEqual(['u1', 'r1']);
    });

    it('says so when the conversation is not found', async () => {
      store.open('c1');
      await settle();
      backend.expectOne('/api/chat/c1/').flush({ error: { code: 'not_found', message: 'Gone' } }, { status: 404, statusText: 'Not Found' });
      backend.expectOne((request) => request.url === '/api/chat/c1/messages/').flush({ error: { code: 'not_found', message: 'Gone' } }, { status: 404, statusText: 'Not Found' });
      await settle();

      expect(store.error()?.code).toBe('not_found');
      expect(store.ready()).toBe(false);
    });

    it('asks again when the page opens the conversation it already holds', async () => {
      await open();

      store.open('c1');
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation({ title: 'Fresh' }));
      backend.expectOne((request) => request.url === '/api/chat/c1/messages/').flush(page([ASKED, SAVED]));
      await settle();

      expect(store.conversation()?.title).toBe('Fresh');
    });

    it('holds nothing when no conversation is open', async () => {
      await open();

      store.open(null);
      await settle();

      expect(store.conversation()).toBeNull();
      expect(store.messages()).toEqual([]);
    });
  });

  describe('sending and streaming', () => {
    it('sends the text and keeps it as a stream until the saved reply arrives', async () => {
      await open([]);

      const sent = store.send('Where is my order?');
      const request = replyRequest();
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({ content: 'Where is my order?' });
      expect(request.request.responseType).toBe('text');
      expect(store.sending()).toBe(true);

      push(request, frame('start', { asked: ASKED, reply: PLACEHOLDER }));
      expect(await sent).toBe(true);
      expect(store.messages().map((row) => row.id)).toEqual(['u1', 'r1']);
      expect(store.stream()).toEqual({ replyId: 'r1', phase: 'loading', thinking: '', content: '', engine: '' });

      push(request, frame('ready', { engine: 'Mesbah' }));
      expect(store.stream()).toMatchObject({ phase: 'writing', engine: 'Mesbah' });

      push(request, frame('thinking', { text: 'Let me ' }) + frame('thinking', { text: 'check.' }));
      expect(store.stream()).toMatchObject({ phase: 'thinking', thinking: 'Let me check.' });

      push(request, frame('content', { text: 'It ships ' }));
      push(request, frame('content', { text: 'tomorrow.' }));
      expect(store.stream()).toMatchObject({ phase: 'writing', thinking: 'Let me check.', content: 'It ships tomorrow.' });
      expect(store.sending()).toBe(true);

      push(request, frame('done', { reply: SAVED }));
      expect(store.messages()[1]).toEqual(SAVED);
      expect(store.stream()).toBeNull();
      expect(store.sending()).toBe(false);

      request.flush(streamed);
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation({ title: 'Where is my order?' }));
      await settle();
      expect(store.conversation()?.title).toBe('Where is my order?');
    });

    it('reads an event that arrives in two pieces', async () => {
      await open([]);
      const sent = store.send('Hi');
      const request = replyRequest();
      const start = frame('start', { asked: ASKED, reply: PLACEHOLDER });

      push(request, start.slice(0, 30));
      expect(store.messages()).toHaveLength(0);
      push(request, start.slice(30));

      expect(await sent).toBe(true);
      expect(store.messages()).toHaveLength(2);
      store.leave();
    });

    it('ignores a keepalive comment', async () => {
      await open([]);
      const { request } = await begin();

      push(request, ': keepalive\n\n');
      push(request, frame('content', { text: 'Hi' }));

      expect(store.stream()?.content).toBe('Hi');
      store.leave();
    });

    it('does not send blank text, or a second message while one is streaming', async () => {
      await open([]);

      expect(await store.send('   ')).toBe(false);
      const first = store.send('One');
      expect(await store.send('Two')).toBe(false);
      const request = replyRequest();
      push(request, frame('start', { asked: ASKED, reply: PLACEHOLDER }));
      await first;
      store.leave();
    });

    it('shows the failure saved with the reply when the engine fails', async () => {
      await open([]);
      const { request } = await begin();
      const failed = message('r1', { status: 'failed', content: '', error_code: 'engine_unreachable' });

      push(request, frame('error', { code: 'engine_unreachable', message: 'The engine isn\'t running.', reply: failed }));

      expect(store.messages()[1].status).toBe('failed');
      expect(store.messages()[1].error_code).toBe('engine_unreachable');
      expect(store.sending()).toBe(false);
      request.flush(streamed);
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation());
    });

    it('reports a refusal before the stream starts, and sends nothing', async () => {
      await open([]);

      const sent = store.send('Hi');
      replyRequest().flush(JSON.stringify({ error: { code: 'no_version', message: 'No version' } }), {
        status: 409,
        statusText: 'Conflict',
      });

      expect(await sent).toBe(false);
      expect(store.sendError()?.code).toBe('no_version');
      expect(store.sendError()?.message).toBe('No version');
      expect(store.sending()).toBe(false);
      expect(store.messages()).toEqual([]);
    });

    it('reloads the reply when the connection drops mid-stream', async () => {
      await open([]);
      const { request } = await begin();
      push(request, frame('content', { text: 'Half' }));

      request.error(new ProgressEvent('error'), { status: 0, statusText: 'Unknown Error' });
      await settle();

      expect(store.sending()).toBe(false);
      expect(store.stream()).toBeNull();
      expect(store.sendError()?.code).toBe('network');
      backend.expectOne('/api/chat/messages/r1/').flush(message('r1', { status: 'stopped', content: 'Half' }));
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation());
      await settle();
      expect(store.messages()[1]).toMatchObject({ status: 'stopped', content: 'Half' });
    });
  });

  describe('stopping', () => {
    it('stops the request, keeps what arrived and loads the saved reply', async () => {
      await open([]);
      const { request } = await begin();
      push(request, frame('ready', { engine: 'Mesbah' }));
      push(request, frame('thinking', { text: 'Hmm. ' }));
      push(request, frame('content', { text: 'Half an answer' }));

      const stopping = store.stop();

      expect(request.cancelled).toBe(true);
      expect(store.sending()).toBe(false);
      expect(store.stream()).toBeNull();
      expect(store.messages()[1]).toMatchObject({ status: 'stopped', content: 'Half an answer', thinking: 'Hmm.' });

      await settle();
      backend.expectOne('/api/chat/messages/r1/').flush(message('r1', { status: 'streaming' }));
      await vi.advanceTimersByTimeAsync(SETTLE_DELAY_MS);
      backend
        .expectOne('/api/chat/messages/r1/')
        .flush(message('r1', { status: 'stopped', content: 'Half an answer', thinking: 'Hmm.', updated_at: '2026-10-18T10:02:00Z' }));
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation());
      await stopping;

      expect(store.messages()[1].updated_at).toBe('2026-10-18T10:02:00Z');
      expect(store.messages()[1].status).toBe('stopped');
    });

    it('keeps the reply as stopped when the server still has not saved it after several tries', async () => {
      await open([]);
      const { request } = await begin();
      push(request, frame('content', { text: 'Half' }));

      const stopping = store.stop();
      for (let attempt = 0; attempt < SETTLE_ATTEMPTS; attempt += 1) {
        await settle();
        backend.expectOne('/api/chat/messages/r1/').flush(message('r1', { status: 'streaming' }));
        await vi.advanceTimersByTimeAsync(SETTLE_DELAY_MS);
      }
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation());
      await stopping;

      expect(store.messages()[1]).toMatchObject({ status: 'stopped', content: 'Half' });
    });

    it('reloads the messages when stopped before the server answered', async () => {
      await open([]);
      const sent = store.send('Hi');
      const request = replyRequest();

      const stopping = store.stop();
      await stopping;

      expect(request.cancelled).toBe(true);
      expect(await sent).toBe(false);
      await settle();
      backend.expectOne((r) => r.url === '/api/chat/c1/messages/').flush(page([ASKED, SAVED]));
      await settle();
      expect(store.messages()).toHaveLength(2);
    });

    it('stops the reply when the page opens another conversation', async () => {
      await open([]);
      const { request } = await begin();

      store.open('c2');

      expect(request.cancelled).toBe(true);
      expect(store.sending()).toBe(false);
      await settle();
      backend.expectOne('/api/chat/c2/').flush(conversation({ id: 'c2' }));
      backend.expectOne((r) => r.url === '/api/chat/c2/messages/').flush(page([]));
    });
  });

  describe('the conversation list', () => {
    it('shows the new message count as soon as the reply starts', async () => {
      const list = TestBed.inject(ConversationsStore);
      list.items.set([conversation({ message_count: 0 })]);
      await open([]);
      expect(list.items()[0].message_count).toBe(0);

      const { request } = await begin();
      await settle();

      expect(list.items()[0].message_count).toBe(2);
      store.leave();
      expect(request.cancelled).toBe(true);
    });

    it('keeps the count and takes the new title when the reply is saved', async () => {
      const list = TestBed.inject(ConversationsStore);
      list.items.set([conversation({ message_count: 0 })]);
      await open([]);
      const { request } = await begin();

      push(request, frame('done', { reply: SAVED }));
      request.flush(streamed);
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation({ title: 'Where is my order?' }));
      await settle();

      expect(list.items()[0]).toMatchObject({ title: 'Where is my order?', message_count: 2 });
    });

    it('counts a reply that was stopped', async () => {
      const list = TestBed.inject(ConversationsStore);
      list.items.set([conversation({ message_count: 0 })]);
      await open([]);
      await begin();

      const stopping = store.stop();
      await settle();
      backend.expectOne('/api/chat/messages/r1/').flush(message('r1', { status: 'stopped', content: '' }));
      await settle();
      backend.expectOne('/api/chat/c1/').flush(conversation());
      await stopping;
      await settle();

      expect(list.items()[0].message_count).toBe(2);
    });

    it('counts the messages a conversation has when it opens', async () => {
      const list = TestBed.inject(ConversationsStore);
      list.items.set([conversation({ message_count: null })]);

      await open([ASKED, SAVED]);
      await settle();

      expect(list.items()[0].message_count).toBe(2);
    });
  });

  describe('correcting a reply', () => {
    it('sends the new text with the time the editor started from, and keeps the answer', async () => {
      await open();
      const reply = store.messages()[1];

      const edited = store.edit(reply, { content: 'It ships today.' });
      await settle();
      const request = backend.expectOne('/api/chat/messages/r1/');
      expect(request.request.method).toBe('PATCH');
      expect(request.request.body).toEqual({ seen: reply.updated_at, content: 'It ships today.' });
      expect(store.working()).toEqual(['r1']);
      request.flush(
        message('r1', {
          content: 'It ships today.',
          original_content: 'It ships tomorrow.',
          content_edited_at: '2026-10-18T10:05:00Z',
          approved: true,
          updated_at: '2026-10-18T10:05:00Z',
        }),
      );

      expect(await edited).toBeNull();
      expect(store.messages()[1]).toMatchObject({ content: 'It ships today.', approved: true });
      expect(store.working()).toEqual([]);
    });

    it('sends the thinking on its own', async () => {
      await open();
      const reply = store.messages()[1];

      const edited = store.edit(reply, { thinking: 'The customer asks about an order.' });
      await settle();
      const request = backend.expectOne('/api/chat/messages/r1/');
      expect(request.request.body).toEqual({ seen: reply.updated_at, thinking: 'The customer asks about an order.' });
      request.flush(message('r1', { thinking: 'The customer asks about an order.', thinking_edited_at: '2026-10-18T10:05:00Z' }));

      expect(await edited).toBeNull();
      expect(store.messages()[1].thinking).toBe('The customer asks about an order.');
    });

    it('switches use for training with the same call', async () => {
      await open();
      const reply = store.messages()[1];

      const switched = store.edit(reply, { include_in_training: false });
      await settle();
      const request = backend.expectOne('/api/chat/messages/r1/');
      expect(request.request.body).toEqual({ seen: reply.updated_at, include_in_training: false });
      request.flush(message('r1', { include_in_training: false }));

      expect(await switched).toBeNull();
      expect(store.messages()[1].include_in_training).toBe(false);
    });

    it('marks a reply approved as it is, and takes the mark back', async () => {
      await open();
      const reply = store.messages()[1];

      const approving = store.approve(reply, true);
      await settle();
      const request = backend.expectOne('/api/chat/messages/r1/approve/');
      expect(request.request.body).toEqual({ approved: true });
      request.flush(message('r1', { approved: true, approved_by: 'rana' }));
      expect(await approving).toBeNull();
      expect(store.messages()[1].approved).toBe(true);

      const withdrawing = store.approve(store.messages()[1], false);
      await settle();
      backend.expectOne('/api/chat/messages/r1/approve/').flush(message('r1', { approved: false }));
      expect(await withdrawing).toBeNull();
      expect(store.messages()[1].approved).toBe(false);
    });

    it('puts one part back as the model wrote it', async () => {
      await open([ASKED, message('r1', { content: 'Edited', original_content: 'It ships tomorrow.', content_edited_at: '2026-10-18T10:05:00Z' })]);
      const reply = store.messages()[1];

      const restoring = store.restore(reply, 'content');
      await settle();
      const request = backend.expectOne('/api/chat/messages/r1/restore/');
      expect(request.request.body).toEqual({ seen: reply.updated_at, part: 'content' });
      request.flush(message('r1', { content: 'It ships tomorrow.' }));

      expect(await restoring).toBeNull();
      expect(store.messages()[1]).toMatchObject({ content: 'It ships tomorrow.', content_edited_at: null });
    });

    it('reloads the reply and says so when someone else changed it', async () => {
      await open();
      const reply = store.messages()[1];

      const edited = store.edit(reply, { content: 'Mine' });
      await settle();
      backend
        .expectOne('/api/chat/messages/r1/')
        .flush({ error: { code: 'message_changed', message: 'Changed' } }, { status: 409, statusText: 'Conflict' });
      await settle();
      backend
        .expectOne((request) => request.url === '/api/chat/messages/r1/' && request.method === 'GET')
        .flush(message('r1', { content: 'Theirs', updated_at: '2026-10-18T10:09:00Z' }));

      expect((await edited)?.code).toBe('message_changed');
      expect(store.messages()[1]).toMatchObject({ content: 'Theirs', updated_at: '2026-10-18T10:09:00Z' });
      expect(store.working()).toEqual([]);
    });

    it('hands any other refusal back and leaves the reply as it was', async () => {
      await open();
      const reply = store.messages()[1];

      const edited = store.edit(reply, { content: 'Mine' });
      await settle();
      backend
        .expectOne('/api/chat/messages/r1/')
        .flush({ error: { code: 'not_editable', message: 'No' } }, { status: 409, statusText: 'Conflict' });

      expect((await edited)?.code).toBe('not_editable');
      expect(store.messages()[1]).toEqual(reply);
    });
  });

  describe('changing the conversation', () => {
    it('sends the change and keeps what the server answers', async () => {
      await open();

      const changing = store.change({ thinking: true });
      await settle();
      const request = backend.expectOne('/api/chat/c1/');
      expect(request.request.method).toBe('PATCH');
      expect(request.request.body).toEqual({ thinking: true });
      expect(store.changing()).toBe(true);
      request.flush(conversation({ thinking: true }));

      expect(await changing).toBeNull();
      expect(store.conversation()?.thinking).toBe(true);
      expect(store.changing()).toBe(false);
    });

    it('hands a refusal back and keeps the conversation as it was', async () => {
      await open();

      const changing = store.change({ version: 'v9' });
      await settle();
      backend.expectOne('/api/chat/c1/').flush({ error: { code: 'not_found', message: 'No such version' } }, { status: 404, statusText: 'Not Found' });

      expect((await changing)?.code).toBe('not_found');
      expect(store.conversation()?.version).toBeNull();
    });
  });

  describe('reading', () => {
    it('lets viewers read and reviewers write', () => {
      expect(store.canWrite()).toBe(true);
    });

    it('names the version that answered, as the project lists it', async () => {
      const list = TestBed.inject(ConversationsStore);
      list.open('p1');
      await settle();
      backend.expectOne((request) => request.url === '/api/chat/' && request.method === 'GET').flush(page([]));
      backend.expectOne('/api/projects/p1/').flush({ system_prompt: '', thinking: false, generation: { temperature: 0.7, top_p: 0.9, max_tokens: 1024 } });
      backend
        .expectOne((request) => request.url === '/api/versions/')
        .flush(page([{ id: 'v0', number: 0, name: 'base', is_active: true }]));
      backend.expectOne((request) => request.url === '/api/serving/engines/').flush(page([]));
      await settle();

      expect(store.versionLabel({ id: 'v0', name: 'base' })).toEqual({ id: 'v0', number: 0, name: 'base' });
      expect(store.versionLabel({ id: 'gone', name: 'Old' })).toBeNull();
      expect(store.versionLabel(null)).toBeNull();
    });
  });
});
