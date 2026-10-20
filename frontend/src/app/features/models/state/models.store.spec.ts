import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Fit, FitSet, HubResult, Inspection, LibraryModel } from '../data/models.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { ModelsStore } from './models.store';

const GIB = 1024 ** 3;
const LIBRARY = '/api/models/';
const HUB = '/api/models/hub/';
const INSPECT = '/api/models/hub/inspect/';

function fit(verdict: Fit['verdict'] = 'fits'): Fit {
  return { verdict, required_bytes: 6 * GIB, available_bytes: 16 * GIB };
}

const FITS: FitSet = { chat: fit(), chat_full: fit('tight'), training: fit('too_large') };

function model(id: string, overrides: Partial<LibraryModel> = {}): LibraryModel {
  return {
    id,
    repo_id: `org/model-${id}`,
    origin: 'hub',
    revision: 'abc',
    family: 'dense_decoder',
    model_type: 'qwen3',
    architecture: {
      family: 'dense_decoder',
      model_type: 'qwen3',
      layers: 36,
      hidden_size: 4096,
      heads: 32,
      kv_heads: 8,
      vocab_size: 151936,
      context_length: 40960,
      experts: null,
      experts_per_token: null,
      expert_size: null,
    },
    parameters: 8_190_735_360,
    active_parameters: 8_190_735_360,
    license: 'apache-2.0',
    gated: false,
    supports_thinking: true,
    has_chat_template: true,
    size_bytes: 16 * GIB,
    downloaded_bytes: 0,
    status: 'ready',
    error_code: '',
    downloaded_at: null,
    created_at: '2026-10-18T00:00:00Z',
    fit: FITS,
    ...overrides,
  };
}

function page<T>(rows: T[], count = rows.length): Page<T> {
  return { count, next: null, previous: null, results: rows };
}

function hubResult(repo: string, overrides: Partial<HubResult> = {}): HubResult {
  return {
    repo_id: repo,
    downloads: 9_000_000,
    likes: 2_100,
    pipeline_tag: 'text-generation',
    parameters: 8_190_735_360,
    license: 'apache-2.0',
    gated: false,
    model_type: 'qwen3',
    supports_thinking: true,
    fit: FITS,
    in_library: null,
    ...overrides,
  };
}

function inspection(repo: string): Inspection {
  return {
    ...hubResult(repo),
    revision: 'abc',
    family: 'dense_decoder',
    architecture: model('x').architecture,
    active_parameters: 8_190_735_360,
    has_chat_template: true,
    downloadable: true,
    size_bytes: 16 * GIB,
    disk_free_bytes: 200 * GIB,
    fits_disk: true,
  };
}

describe('ModelsStore', () => {
  let store: ModelsStore;
  let backend: HttpTestingController;

  function library(): TestRequest {
    return backend.expectOne((request) => request.url === LIBRARY && request.method === 'GET');
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function loadLibrary(rows: LibraryModel[], count = rows.length): Promise<void> {
    const loading = store.load();
    library().flush(page(rows, count));
    await loading;
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        ModelsStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: (names: readonly string[]) => names.includes('trainers') } },
      ],
    });
    store = TestBed.inject(ModelsStore);
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

  it('asks for the page the paginator shows', async () => {
    const loading = store.load(1, 50);
    const request = library();
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('50');
    request.flush(page([model('1')], 60));
    await loading;

    expect(store.pageIndex()).toBe(1);
    expect(store.page().count).toBe(60);
  });

  it('lets trainers and above change the library', () => {
    expect(store.canWrite()).toBe(true);
  });

  describe('while a download runs', () => {
    beforeEach(async () => {
      await settle();
      backend.expectOne((request) => request.url === HUB).flush(page([]));
      await settle();
    });

    it('refreshes every two seconds and stops once nothing is downloading', async () => {
      const watching = store.watchDownloads().subscribe();
      await loadLibrary([model('1', { status: 'downloading', downloaded_bytes: GIB })]);
      expect(store.downloading()).toBe(true);

      await vi.advanceTimersByTimeAsync(1999);
      backend.expectNone((request) => request.url === LIBRARY);

      await vi.advanceTimersByTimeAsync(1);
      library().flush(page([model('1', { status: 'downloading', downloaded_bytes: 4 * GIB })]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.page().results[0].downloaded_bytes).toBe(4 * GIB);

      await vi.advanceTimersByTimeAsync(2000);
      library().flush(page([model('1', { status: 'ready', downloaded_bytes: 16 * GIB })]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.downloading()).toBe(false);

      await vi.advanceTimersByTimeAsync(10_000);
      backend.expectNone((request) => request.url === LIBRARY);
      watching.unsubscribe();
    });

    it('does not poll once the page stops watching', async () => {
      const watching = store.watchDownloads().subscribe();
      await loadLibrary([model('1', { status: 'queued' })]);
      watching.unsubscribe();

      await vi.advanceTimersByTimeAsync(10_000);
      backend.expectNone((request) => request.url === LIBRARY);
    });

    it('keeps the last list when a background refresh fails', async () => {
      const watching = store.watchDownloads().subscribe();
      await loadLibrary([model('1', { status: 'downloading' })]);

      await vi.advanceTimersByTimeAsync(2000);
      library().flush({}, { status: 500, statusText: 'Server Error' });
      await vi.advanceTimersByTimeAsync(0);

      expect(store.page().results).toHaveLength(1);
      expect(store.error()).toBeNull();
      watching.unsubscribe();
    });

    it('starts polling again when a retry queues the download', async () => {
      const watching = store.watchDownloads().subscribe();
      await loadLibrary([model('1', { status: 'failed', error_code: 'network' })]);
      expect(store.downloading()).toBe(false);

      const retrying = store.retry(model('1'));
      backend.expectOne('/api/models/1/retry/').flush(model('1', { status: 'queued' }));
      expect(await retrying).toBe(true);
      expect(store.downloading()).toBe(true);

      await vi.advanceTimersByTimeAsync(2000);
      library().flush(page([model('1', { status: 'downloading' })]));
      await vi.advanceTimersByTimeAsync(0);
      watching.unsubscribe();
    });
  });

  it('replaces only the cancelled row', async () => {
    await loadLibrary([model('1', { status: 'downloading' }), model('2')]);

    const cancelling = store.cancel(model('1'));
    backend.expectOne('/api/models/1/cancel/').flush(model('1', { status: 'cancelled' }));

    expect(await cancelling).toBe(true);
    expect(store.page().results.map((row) => row.status)).toEqual(['cancelled', 'ready']);
    expect(store.working()).toEqual([]);
  });

  it('reports a refused removal and keeps the row', async () => {
    await loadLibrary([model('1')]);

    const removing = store.remove(model('1'));
    backend
      .expectOne((request) => request.method === 'DELETE')
      .flush({ error: { code: 'forbidden', message: 'No.' } }, { status: 400, statusText: 'Bad Request' });

    expect(await removing).toBe(false);
    expect(store.error()?.code).toBe('forbidden');
    expect(store.page().results).toHaveLength(1);
  });

  it('steps back a page when the last row of the last page is removed', async () => {
    const loading = store.load(1, 1);
    library().flush(page([model('2')], 2));
    await loading;

    const removing = store.remove(model('2'));
    backend.expectOne((request) => request.method === 'DELETE').flush(null, { status: 204, statusText: 'No Content' });
    await vi.advanceTimersByTimeAsync(0);
    const reload = library();
    expect(reload.request.params.get('page')).toBe('1');
    reload.flush(page([model('1')], 1));
    await settle();
    backend.expectOne((request) => request.url === HUB).flush(page([hubResult('org/model-1')]));

    expect(await removing).toBe(true);
    expect(store.pageIndex()).toBe(0);
  });

  describe('adding a model', () => {
    it('reloads the library from the first page and refreshes the search', async () => {
      await settle();
      backend.expectOne((request) => request.url === HUB).flush(page([hubResult('org/model-1')]));
      await settle();

      const adding = store.add('org/model-1');
      const request = backend.expectOne((r) => r.url === LIBRARY && r.method === 'POST');
      expect(request.request.body).toEqual({ repo_id: 'org/model-1' });
      request.flush(model('1', { status: 'queued' }), { status: 202, statusText: 'Accepted' });
      await vi.advanceTimersByTimeAsync(0);
      library().flush(page([model('1', { status: 'queued' })]));
      await settle();
      backend
        .expectOne((r) => r.url === HUB)
        .flush(page([hubResult('org/model-1', { in_library: { id: '1', status: 'queued' } })]));
      await settle();

      expect(await adding).toBeNull();
      expect(store.hubResults()[0].in_library?.status).toBe('queued');
    });

    it('hands the refusal back in the reader\'s language', async () => {
      const locale = TestBed.inject(LocaleStore);
      locale.register({ en, ar });
      locale.setLocale('en');

      const adding = store.add('org/model-1');
      backend
        .expectOne((r) => r.url === LIBRARY && r.method === 'POST')
        .flush(
          { error: { code: 'already_in_library', message: 'raw' } },
          { status: 409, statusText: 'Conflict' },
        );

      const failure = await adding;
      expect(failure?.code).toBe('already_in_library');
      expect(failure?.message).toBe(en.errors.already_in_library);
      expect(store.adding()).toBe(false);
    });
  });

  describe('searching HuggingFace', () => {
    it('shows the popular list without parameters', async () => {
      await settle();
      const request = backend.expectOne((r) => r.url === HUB);
      expect(request.request.params.keys()).toEqual([]);
      request.flush(page([hubResult('Qwen/Qwen3-8B')]));
      await settle();

      expect(store.hubResults().map((result) => result.repo_id)).toEqual(['Qwen/Qwen3-8B']);
      expect(store.hubLoading()).toBe(false);
    });

    it('sends the search and the task', async () => {
      await settle();
      backend.expectOne((r) => r.url === HUB).flush(page([]));
      await settle();

      store.search({ search: '  qwen ', task: 'text2text-generation' });
      await settle();
      const request = backend.expectOne((r) => r.url === HUB);
      expect(request.request.params.get('search')).toBe('qwen');
      expect(request.request.params.get('task')).toBe('text2text-generation');
      request.flush(page([hubResult('Qwen/Qwen3-8B')]));
      await settle();

      expect(store.hubQuery().search).toBe('qwen');
      expect(store.hubResults()).toHaveLength(1);
    });

    it('keeps the reason and tries again', async () => {
      await settle();
      backend
        .expectOne((r) => r.url === HUB)
        .flush({ error: { code: 'hf_unreachable', message: 'Down.' } }, { status: 503, statusText: 'Unavailable' });
      await settle();

      expect(store.hubError()?.code).toBe('hf_unreachable');
      expect(store.hubResults()).toEqual([]);

      store.searchAgain();
      await settle();
      backend.expectOne((r) => r.url === HUB).flush(page([hubResult('Qwen/Qwen3-8B')]));
      await settle();

      expect(store.hubError()).toBeNull();
      expect(store.hubResults()).toHaveLength(1);
    });
  });

  describe('inspecting a model', () => {
    it('loads nothing until a model is chosen, then forgets it when the dialog closes', async () => {
      await settle();
      backend.expectOne((r) => r.url === HUB).flush(page([]));
      await settle();
      expect(store.inspection()).toBeNull();

      store.inspect('Qwen/Qwen3-8B');
      await settle();
      const request = backend.expectOne((r) => r.url === INSPECT);
      expect(request.request.params.get('repo')).toBe('Qwen/Qwen3-8B');
      expect(store.inspecting()).toBe(true);
      request.flush(inspection('Qwen/Qwen3-8B'));
      await settle();

      expect(store.inspection()?.downloadable).toBe(true);

      store.stopInspecting();
      await settle();
      expect(store.inspection()).toBeNull();
    });

    it('reports a model that HuggingFace does not know', async () => {
      await settle();
      backend.expectOne((r) => r.url === HUB).flush(page([]));
      await settle();

      store.inspect('nobody/nothing');
      await settle();
      backend
        .expectOne((r) => r.url === INSPECT)
        .flush(
          { error: { code: 'hub_model_not_found', message: 'None.' } },
          { status: 404, statusText: 'Not Found' },
        );
      await settle();

      expect(store.inspectionError()?.code).toBe('hub_model_not_found');
      expect(store.inspection()).toBeNull();
    });
  });
});
