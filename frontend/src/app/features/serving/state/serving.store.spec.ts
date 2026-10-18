import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import type { ApiKey, CreatedApiKey, Engine, EngineState } from '../data/serving.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { ServingStore } from './serving.store';

const ENGINES = '/api/serving/engines/';
const KEYS = '/api/serving/keys/';
const PROJECTS = '/api/projects/';
const SECRET = 'msb_example-secret-shown-once';

let groups: readonly string[] = ['trainers', 'admins'];

const IDLE: EngineState = {
  running: true,
  loaded: false,
  busy: false,
  device: null,
  quantized: false,
  base_model: null,
  versions: [],
};

function engine(id: string, overrides: Partial<Engine> = {}): Engine {
  return {
    id,
    name: `Engine ${id}`,
    kind: 'openai',
    base_url: `http://gpu-${id}:8000`,
    model_name: '',
    has_api_key: false,
    enabled: true,
    is_default: false,
    last_seen_at: null,
    state: IDLE,
    ...overrides,
  };
}

function builtin(overrides: Partial<Engine> = {}): Engine {
  return engine('builtin', {
    name: 'Mesbah',
    kind: 'builtin',
    is_default: true,
    base_url: 'http://127.0.0.1:8078',
    ...overrides,
  });
}

function key(id: string, overrides: Partial<ApiKey> = {}): ApiKey {
  return {
    id,
    name: `Key ${id}`,
    prefix: 'msb_abcd1234',
    owner: 'tariq',
    last_used_at: null,
    created_at: '2026-10-18T00:00:00Z',
    ...overrides,
  };
}

function page<T>(rows: T[], count = rows.length): Page<T> {
  return { count, next: null, previous: null, results: rows };
}

describe('ServingStore', () => {
  let store: ServingStore;
  let backend: HttpTestingController;

  function engines(): TestRequest {
    return backend.expectOne((request) => request.url === ENGINES && request.method === 'GET');
  }

  function keysList(): TestRequest {
    return backend.expectOne((request) => request.url === KEYS && request.method === 'GET');
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function open(rows: Engine[] = [builtin()], slugs: string[] = []): Promise<void> {
    const visiting = store.visit();
    engines().flush(page(rows));
    if (store.canTrain()) {
      keysList().flush(page([]));
    }
    await visiting;
    await settle();
    for (const request of backend.match((r) => r.url === PROJECTS)) {
      request.flush(page(slugs.map((slug) => ({ slug }))));
    }
    await settle();
  }

  function configure(): void {
    TestBed.configureTestingModule({
      providers: [
        ServingStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: (names: readonly string[]) => names.some((n) => groups.includes(n)) } },
      ],
    });
    store = TestBed.inject(ServingStore);
    backend = TestBed.inject(HttpTestingController);
  }

  async function answerExamples(slugs: string[]): Promise<void> {
    await settle();
    backend
      .expectOne((request) => request.url === PROJECTS)
      .flush(page(slugs.map((slug) => ({ slug }))));
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    groups = ['trainers', 'admins'];
    configure();
  });

  afterEach(() => {
    try {
      backend.verify();
    } finally {
      TestBed.resetTestingModule();
      vi.useRealTimers();
    }
  });

  describe('loading', () => {
    beforeEach(async () => {
      await answerExamples(['support-assistant', 'engine-check']);
    });

    it('asks for the engines and, for trainers, the first page of keys', async () => {
      const visiting = store.visit();
      const request = engines();
      expect(request.request.params.get('page_size')).toBe('200');
      request.flush(page([builtin(), engine('1')]));
      const keysRequest = keysList();
      expect(keysRequest.request.params.get('page')).toBe('1');
      keysRequest.flush(page([key('1')]));
      await visiting;
      await settle();
      backend.expectOne((r) => r.url === PROJECTS).flush(page([{ slug: 'support-assistant' }]));
      await settle();

      expect(store.builtin()?.kind).toBe('builtin');
      expect(store.others().map((row) => row.id)).toEqual(['1']);
      expect(store.keys().count).toBe(1);
      expect(store.loaded()).toBe(true);
    });

    it('leaves the keys alone for a reader below trainers', async () => {
      groups = ['reviewers'];
      expect(store.canTrain()).toBe(false);
      expect(store.canManage()).toBe(false);

      const visiting = store.visit();
      engines().flush(page([builtin()]));
      await visiting;
      await settle();
      backend.expectOne((r) => r.url === PROJECTS).flush(page([]));
      await settle();

      backend.expectNone((request) => request.url === KEYS);
    });

    it('names the first project in the examples, or a placeholder when there is none', async () => {
      expect(store.exampleSlug()).toBe('support-assistant');

      await open([builtin()], []);

      expect(store.exampleSlug()).toBe('my-project');
    });

    it('lists the default engine first among the others', async () => {
      await open([builtin({ is_default: false }), engine('1'), engine('2', { is_default: true })]);
      await settle();

      expect(store.others().map((row) => row.id)).toEqual(['2', '1']);
    });

    it('keeps the reason when the engines cannot be loaded', async () => {
      const locale = TestBed.inject(LocaleStore);
      locale.register({ en, ar });
      locale.setLocale('en');
      const loading = store.load();
      engines().flush(
        { error: { code: 'engine_failed', message: 'raw' } },
        { status: 502, statusText: 'Bad Gateway' },
      );
      await loading;

      expect(store.error()?.code).toBe('engine_failed');
      expect(store.error()?.message).toBe(en.errors.engine_failed);
      expect(store.loaded()).toBe(false);
      expect(store.loading()).toBe(false);
    });
  });

  describe('changing engines', () => {
    beforeEach(async () => {
      await answerExamples([]);
      await open([builtin(), engine('1'), engine('2')]);
    });

    it('replaces only the changed row', async () => {
      const turningOff = store.change(engine('2'), { enabled: false });
      const request = backend.expectOne(`${ENGINES}2/`);
      expect(request.request.method).toBe('PATCH');
      expect(request.request.body).toEqual({ enabled: false });
      request.flush(engine('2', { enabled: false }));

      expect(await turningOff).toBe(true);
      expect(store.others().map((row) => row.enabled)).toEqual([true, false]);
      expect(store.working()).toEqual([]);
    });

    it('moves the default marker to the engine that took it', async () => {
      const making = store.change(engine('1'), { is_default: true });
      backend.expectOne(`${ENGINES}1/`).flush(engine('1', { is_default: true }));
      await making;

      expect(store.builtin()?.is_default).toBe(false);
      expect(store.others().map((row) => [row.id, row.is_default])).toEqual([
        ['1', true],
        ['2', false],
      ]);
    });

    it('reports a refused change and keeps the row as it was', async () => {
      const changing = store.change(engine('1'), { enabled: false });
      backend
        .expectOne(`${ENGINES}1/`)
        .flush({ error: { code: 'forbidden', message: 'No.' } }, { status: 400, statusText: 'Bad Request' });

      expect(await changing).toBe(false);
      expect(store.error()?.code).toBe('forbidden');
      expect(store.others()[0].enabled).toBe(true);
    });

    it('hands a refused save back to the dialog', async () => {
      const saving = store.save(engine('1'), { base_url: 'nope' });
      backend
        .expectOne(`${ENGINES}1/`)
        .flush({ error: { code: 'address', message: 'Bad.' } }, { status: 400, statusText: 'Bad Request' });

      expect((await saving)?.code).toBe('address');
      expect(store.saving()).toBe(false);
    });

    it('sends an empty key to remove it', async () => {
      const saving = store.save(engine('1', { has_api_key: true }), { api_key: '' });
      const request = backend.expectOne(`${ENGINES}1/`);
      expect(request.request.body).toEqual({ api_key: '' });
      request.flush(engine('1', { has_api_key: false }));

      expect(await saving).toBeNull();
      expect(store.others()[0].has_api_key).toBe(false);
    });
  });

  describe('connecting and disconnecting', () => {
    beforeEach(async () => {
      await answerExamples([]);
      await open([builtin()]);
    });

    it('posts the engine and then reloads the list', async () => {
      const connecting = store.connect({ name: 'GPU box', kind: 'openai', base_url: 'http://127.0.0.1:9' });
      const post = backend.expectOne((r) => r.url === ENGINES && r.method === 'POST');
      expect(post.request.body).toEqual({ name: 'GPU box', kind: 'openai', base_url: 'http://127.0.0.1:9' });
      post.flush(engine('1'), { status: 201, statusText: 'Created' });
      await vi.advanceTimersByTimeAsync(0);
      engines().flush(page([builtin(), engine('1')]));

      expect(await connecting).toBeNull();
      expect(store.others().map((row) => row.id)).toEqual(['1']);
      expect(store.saving()).toBe(false);
    });

    it('hands a refusal back in the reader\'s language', async () => {
      const locale = TestBed.inject(LocaleStore);
      locale.register({ en, ar });
      locale.setLocale('en');

      const connecting = store.connect({ name: 'x', kind: 'vllm', base_url: 'http://x' });
      backend
        .expectOne((r) => r.url === ENGINES && r.method === 'POST')
        .flush({ error: { code: 'engine_unreachable', message: 'raw' } }, { status: 503, statusText: 'Unavailable' });

      const failure = await connecting;
      expect(failure?.code).toBe('engine_unreachable');
      expect(failure?.message).toBe(en.errors.engine_unreachable);
    });

    it('takes the row away at once and reloads', async () => {
      await open([builtin(), engine('1')]);

      const disconnecting = store.disconnect(engine('1'));
      backend.expectOne((r) => r.url === `${ENGINES}1/` && r.method === 'DELETE').flush(null, {
        status: 204,
        statusText: 'No Content',
      });
      await vi.advanceTimersByTimeAsync(0);
      expect(store.others()).toEqual([]);
      engines().flush(page([builtin()]));

      expect(await disconnecting).toBe(true);
      expect(store.others()).toEqual([]);
    });

    it('keeps Mesbah\'s own engine and says so', async () => {
      TestBed.inject(LocaleStore).register({ en, ar });
      const disconnecting = store.disconnect(builtin());
      backend
        .expectOne((r) => r.method === 'DELETE')
        .flush({ error: { code: 'builtin_engine_kept', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

      expect(await disconnecting).toBe(false);
      expect(store.error()?.code).toBe('builtin_engine_kept');
      expect(store.builtin()).not.toBeNull();
    });
  });

  describe('freeing memory', () => {
    beforeEach(async () => {
      await answerExamples([]);
    });

    it('replaces the engine with the answer, nothing loaded', async () => {
      const loadedState: EngineState = {
        ...IDLE,
        loaded: true,
        device: 'cpu',
        base_model: { id: 'm1', repo_id: 'org/tiny' },
      };
      await open([builtin({ state: loadedState })]);
      expect(store.builtin()?.state.loaded).toBe(true);

      const freeing = store.unload(builtin());
      const request = backend.expectOne(`${ENGINES}builtin/unload/`);
      expect(request.request.method).toBe('POST');
      request.flush(builtin());

      expect(await freeing).toBe(true);
      expect(store.builtin()?.state.loaded).toBe(false);
    });

    it('reports an engine that cannot be reached', async () => {
      await open([builtin()]);

      const freeing = store.unload(builtin());
      backend
        .expectOne(`${ENGINES}builtin/unload/`)
        .flush({ error: { code: 'engine_unreachable', message: 'Down.' } }, { status: 503, statusText: 'Unavailable' });

      expect(await freeing).toBe(false);
      expect(store.error()?.code).toBe('engine_unreachable');
    });
  });

  describe('API keys', () => {
    beforeEach(async () => {
      await answerExamples([]);
      await open();
    });

    it('asks for the page the paginator shows', async () => {
      const loading = store.loadKeys(1, 25);
      const request = keysList();
      expect(request.request.params.get('page')).toBe('2');
      expect(request.request.params.get('page_size')).toBe('25');
      request.flush(page([key('1')], 30));
      await loading;

      expect(store.keysPageIndex()).toBe(1);
      expect(store.keys().count).toBe(30);
    });

    it('gives the new key once and never keeps it', async () => {
      const creating = store.createKey('CI');
      const post = backend.expectOne((r) => r.url === KEYS && r.method === 'POST');
      expect(post.request.body).toEqual({ name: 'CI' });
      const created: CreatedApiKey = { ...key('9', { name: 'CI' }), key: SECRET };
      post.flush(created, { status: 201, statusText: 'Created' });

      const result = await creating;
      expect('key' in result && result.key.key).toBe(SECRET);
      keysList().flush(page([key('9', { name: 'CI' })]));
      await vi.advanceTimersByTimeAsync(0);

      expect(JSON.stringify(store.keys())).not.toContain(SECRET);
      expect(store.keysPageIndex()).toBe(0);
      expect(store.creatingKey()).toBe(false);
    });

    it('hands a refusal back to the dialog', async () => {
      const creating = store.createKey('');
      backend
        .expectOne((r) => r.url === KEYS && r.method === 'POST')
        .flush({ error: { code: 'invalid', message: 'Name it.' } }, { status: 400, statusText: 'Bad Request' });

      const result = await creating;
      expect('error' in result && result.error.code).toBe('invalid');
    });

    it('revokes a key and reloads the page', async () => {
      const loading = store.loadKeys();
      keysList().flush(page([key('1'), key('2')]));
      await loading;

      const revoking = store.revokeKey(key('1'));
      backend.expectOne((r) => r.url === `${KEYS}1/` && r.method === 'DELETE').flush(null, {
        status: 204,
        statusText: 'No Content',
      });
      await vi.advanceTimersByTimeAsync(0);
      keysList().flush(page([key('2')]));

      expect(await revoking).toBe(true);
      expect(store.keys().results.map((row) => row.id)).toEqual(['2']);
      expect(store.keyWorking()).toEqual([]);
    });

    it('steps back a page when the last key of the last page is revoked', async () => {
      const loading = store.loadKeys(1, 1);
      keysList().flush(page([key('2')], 2));
      await loading;

      const revoking = store.revokeKey(key('2'));
      backend.expectOne((r) => r.method === 'DELETE').flush(null, { status: 204, statusText: 'No Content' });
      await vi.advanceTimersByTimeAsync(0);
      const reload = keysList();
      expect(reload.request.params.get('page')).toBe('1');
      reload.flush(page([key('1')], 1));

      expect(await revoking).toBe(true);
      expect(store.keysPageIndex()).toBe(0);
    });

    it('reports a refused revoke and keeps the key', async () => {
      const loading = store.loadKeys();
      keysList().flush(page([key('1')]));
      await loading;

      const revoking = store.revokeKey(key('1'));
      backend
        .expectOne((r) => r.method === 'DELETE')
        .flush({ error: { code: 'not_found', message: 'Gone.' } }, { status: 404, statusText: 'Not Found' });

      expect(await revoking).toBe(false);
      expect(store.keysError()?.code).toBe('not_found');
      expect(store.keys().results).toHaveLength(1);
    });
  });

  describe('watching', () => {
    beforeEach(async () => {
      await answerExamples([]);
      await open([builtin()]);
    });

    it('refreshes every five seconds and stops when the page stops watching', async () => {
      const watching = store.watch().subscribe();

      await vi.advanceTimersByTimeAsync(4999);
      backend.expectNone((r) => r.url === ENGINES);

      await vi.advanceTimersByTimeAsync(1);
      engines().flush(page([builtin({ state: { ...IDLE, busy: true } })]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.builtin()?.state.busy).toBe(true);

      await vi.advanceTimersByTimeAsync(5000);
      engines().flush(page([builtin()]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.builtin()?.state.busy).toBe(false);

      watching.unsubscribe();
      await vi.advanceTimersByTimeAsync(20_000);
      backend.expectNone((r) => r.url === ENGINES);
    });

    it('keeps the last state when a refresh fails', async () => {
      const watching = store.watch().subscribe();

      await vi.advanceTimersByTimeAsync(5000);
      engines().flush({}, { status: 500, statusText: 'Server Error' });
      await vi.advanceTimersByTimeAsync(0);

      expect(store.builtin()).not.toBeNull();
      expect(store.error()).toBeNull();

      await vi.advanceTimersByTimeAsync(5000);
      engines().flush(page([builtin()]));
      await vi.advanceTimersByTimeAsync(0);
      watching.unsubscribe();
    });

    it('drops an answer that was asked for before a change landed', async () => {
      await open([builtin(), engine('1')]);
      const watching = store.watch().subscribe();

      await vi.advanceTimersByTimeAsync(5000);
      const stale = engines();

      const turningOff = store.change(engine('1'), { enabled: false });
      backend.expectOne(`${ENGINES}1/`).flush(engine('1', { enabled: false }));
      await turningOff;

      stale.flush(page([builtin(), engine('1')]));
      await vi.advanceTimersByTimeAsync(0);

      expect(store.others()[0].enabled).toBe(false);
      watching.unsubscribe();
    });
  });
});
