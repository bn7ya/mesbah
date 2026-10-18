import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import type { Conversation, EngineOption, ProjectDefaults, VersionOption } from '../data/chat.types';
import { ConversationsStore } from './conversations.store';

function conversation(id: string, overrides: Partial<Conversation> = {}): Conversation {
  return {
    id,
    project: 'p1',
    title: `Conversation ${id}`,
    version: null,
    engine: null,
    system_prompt: '',
    thinking: false,
    generation: {},
    message_count: 2,
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T10:00:00Z',
    ...overrides,
  };
}

function page<T>(rows: T[], overrides: Partial<Page<T>> = {}): Page<T> {
  return { count: rows.length, next: null, previous: null, results: rows, ...overrides };
}

const DEFAULTS: ProjectDefaults = {
  system_prompt: 'You are a friendly support agent.',
  thinking: false,
  generation: { temperature: 0.7, top_p: 0.9, max_tokens: 1024 },
};

const VERSIONS: VersionOption[] = [
  { id: 'v0', number: 0, name: 'base', is_active: false },
  { id: 'v1', number: 1, name: 'Friendlier', is_active: true },
];

const ENGINES: EngineOption[] = [
  { id: 'e1', name: 'Mesbah', enabled: true, is_default: true },
  { id: 'e2', name: 'Old engine', enabled: false, is_default: false },
];

describe('ConversationsStore', () => {
  let store: ConversationsStore;
  let backend: HttpTestingController;
  let groups: readonly string[];

  function conversations(): TestRequest {
    return backend.expectOne((request) => request.url === '/api/chat/' && request.method === 'GET');
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function open(rows: Conversation[] = [conversation('c1'), conversation('c2')]): Promise<void> {
    store.open('p1');
    await settle();
    conversations().flush(page(rows));
    backend.expectOne('/api/projects/p1/').flush(DEFAULTS);
    backend.expectOne((request) => request.url === '/api/versions/').flush(page(VERSIONS));
    backend.expectOne((request) => request.url === '/api/serving/engines/').flush(page(ENGINES));
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    groups = ['reviewers'];
    TestBed.configureTestingModule({
      providers: [
        ConversationsStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: (names: readonly string[]) => names.some((name) => groups.includes(name)) } },
      ],
    });
    store = TestBed.inject(ConversationsStore);
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

  it('asks for the project\'s conversations and shows them', async () => {
    store.open('p1');
    await settle();
    const request = conversations();
    expect(request.request.params.get('project')).toBe('p1');
    expect(request.request.params.get('page')).toBe('1');
    expect(store.loading()).toBe(true);
    request.flush(page([conversation('c1')]));
    backend.expectOne('/api/projects/p1/').flush(DEFAULTS);
    backend.expectOne((r) => r.url === '/api/versions/').flush(page(VERSIONS));
    backend.expectOne((r) => r.url === '/api/serving/engines/').flush(page(ENGINES));
    await settle();

    expect(store.loading()).toBe(false);
    expect(store.items().map((row) => row.id)).toEqual(['c1']);
  });

  it('reads what the header needs: the project\'s settings, its versions and the engines that are on', async () => {
    await open();

    expect(store.defaults()).toEqual(DEFAULTS);
    expect(store.versions().map((row) => row.id)).toEqual(['v0', 'v1']);
    expect(store.activeVersion()?.id).toBe('v1');
    expect(store.engines().map((row) => row.id)).toEqual(['e1']);
  });

  it('loads the next page and adds it below', async () => {
    store.open('p1');
    await settle();
    conversations().flush(page([conversation('c1')], { count: 2, next: 'http://x/?page=2' }));
    backend.expectOne('/api/projects/p1/').flush(DEFAULTS);
    backend.expectOne((r) => r.url === '/api/versions/').flush(page(VERSIONS));
    backend.expectOne((r) => r.url === '/api/serving/engines/').flush(page(ENGINES));
    await settle();
    expect(store.nextPage()).toBe(2);

    store.more();
    await settle();
    const second = conversations();
    expect(second.request.params.get('page')).toBe('2');
    second.flush(page([conversation('c2')], { count: 2 }));
    await settle();

    expect(store.items().map((row) => row.id)).toEqual(['c1', 'c2']);
    expect(store.nextPage()).toBeNull();
  });

  it('shows a failed load and tries again', async () => {
    store.open('p1');
    await settle();
    conversations().flush({ error: { code: 'unknown', message: 'Nope' } }, { status: 500, statusText: 'Error' });
    backend.expectOne('/api/projects/p1/').flush(DEFAULTS);
    backend.expectOne((r) => r.url === '/api/versions/').flush(page(VERSIONS));
    backend.expectOne((r) => r.url === '/api/serving/engines/').flush(page(ENGINES));
    await settle();
    expect(store.error()?.message).toBe('Nope');

    store.reload();
    await settle();
    conversations().flush(page([conversation('c1')]));
    await settle();

    expect(store.error()).toBeNull();
    expect(store.items()).toHaveLength(1);
  });

  it('starts a conversation in the project and puts it first', async () => {
    await open();

    const created = store.create();
    await settle();
    const request = backend.expectOne((r) => r.url === '/api/chat/' && r.method === 'POST');
    expect(request.request.body).toEqual({ project: 'p1' });
    request.flush(conversation('c3', { title: '' }));
    const result = await created;

    expect(result).toEqual({ conversation: conversation('c3', { title: '' }) });
    expect(store.items().map((row) => row.id)).toEqual(['c3', 'c1', 'c2']);
    expect(store.creating()).toBe(false);
  });

  it('hands a refused start back', async () => {
    await open();

    const created = store.create();
    await settle();
    backend
      .expectOne((r) => r.method === 'POST')
      .flush({ error: { code: 'no_version', message: 'No version' } }, { status: 409, statusText: 'Conflict' });
    const result = await created;

    expect('error' in result && result.error.code).toBe('no_version');
    expect(store.items()).toHaveLength(2);
  });

  it('removes a conversation from the list', async () => {
    await open();

    const removed = store.remove(store.items()[0]);
    await settle();
    backend.expectOne('/api/chat/c1/').flush(null, { status: 204, statusText: 'No Content' });

    expect(await removed).toBeNull();
    expect(store.items().map((row) => row.id)).toEqual(['c2']);
  });

  it('keeps a conversation the server refused to remove', async () => {
    await open();

    const removed = store.remove(store.items()[0]);
    await settle();
    backend.expectOne('/api/chat/c1/').flush({ error: { code: 'refused', message: 'No' } }, { status: 409, statusText: 'Conflict' });

    expect((await removed)?.code).toBe('refused');
    expect(store.items()).toHaveLength(2);
  });

  it('moves a changed conversation to the top and keeps its message count', async () => {
    await open([
      conversation('c1', { updated_at: '2026-10-18T10:00:00Z', message_count: 4 }),
      conversation('c2', { updated_at: '2026-10-18T11:00:00Z' }),
    ]);
    expect(store.items().map((row) => row.id)).toEqual(['c1', 'c2']);

    store.replace(conversation('c1', { title: 'Renamed', updated_at: '2026-10-18T12:00:00Z', message_count: null }));

    expect(store.items().map((row) => row.id)).toEqual(['c1', 'c2']);
    expect(store.items()[0].title).toBe('Renamed');
    expect(store.items()[0].message_count).toBe(4);

    store.replace(conversation('c2', { updated_at: '2026-10-18T13:00:00Z' }));

    expect(store.items().map((row) => row.id)).toEqual(['c2', 'c1']);
  });

  it('lets reviewers write', () => {
    expect(store.canWrite()).toBe(true);
  });

  it('lets viewers read only', () => {
    groups = ['viewers'];

    expect(store.canWrite()).toBe(false);
  });
});
