import { HttpEventType, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Conversation, Dataset, HubDataset, Inspection, Mapping } from '../data/datasets.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { DatasetsStore } from './datasets.store';

const LIBRARY = '/api/datasets/';
const HUB = '/api/datasets/hub/';
const INSPECT = '/api/datasets/hub/inspect/';
const UPLOAD = '/api/datasets/upload/';

const MAPPING: Mapping = {
  format: 'instruction',
  conversation: '',
  system: '',
  prompt: 'instruction',
  input: 'input',
  reply: 'output',
  thinking: '',
  text: '',
};

function dataset(id: string, overrides: Partial<Dataset> = {}): Dataset {
  return {
    id,
    name: `org/data-${id}`,
    description: '',
    source: 'hub',
    repo_id: `org/data-${id}`,
    config_name: 'default',
    split: 'train',
    file_name: '',
    format: 'instruction',
    mapping: MAPPING,
    row_limit: 10_000,
    source_rows: 52_002,
    status: 'ready',
    error_code: '',
    rows: 10_000,
    skipped: 3,
    size_bytes: 4_200_000,
    sha256: 'abc',
    has_thinking: false,
    excerpt: 'Give three tips.',
    created_by: 'Sara',
    created_at: '2026-10-18T00:00:00Z',
    ...overrides,
  };
}

function page<T>(rows: T[], count = rows.length): Page<T> {
  return { count, next: null, previous: null, results: rows };
}

function hubDataset(repo: string): HubDataset {
  return {
    repo_id: repo,
    downloads: 82_940,
    likes: 1_387,
    license: 'cc-by-nc-4.0',
    gated: false,
    size_category: '10K<n<100K',
    languages: ['en'],
    description: 'Instructions and demonstrations.',
    in_library: false,
  };
}

function inspection(repo: string): Inspection {
  return {
    ...hubDataset(repo),
    configs: [{ name: 'default', splits: [{ name: 'train', rows: 52_002 }] }],
    config: 'default',
    split: 'train',
    columns: ['instruction', 'input', 'output'],
    detected: 'instruction',
    mapping: MAPPING,
    conversations: [
      {
        index: 0,
        messages: [
          { role: 'user', content: 'Give three tips.', thinking: '' },
          { role: 'assistant', content: 'Eat, move, sleep.', thinking: '' },
        ],
        text: '',
      },
    ],
    sample_rows: 100,
    sample_skipped: 0,
  };
}

function conversation(index: number): Conversation {
  return { index, messages: [], text: `Line ${index}` };
}

describe('DatasetsStore', () => {
  let store: DatasetsStore;
  let backend: HttpTestingController;

  function library(): TestRequest {
    return backend.expectOne((request) => request.url === LIBRARY && request.method === 'GET');
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function loadLibrary(rows: Dataset[], count = rows.length): Promise<void> {
    const loading = store.load();
    library().flush(page(rows, count));
    await loading;
  }

  async function answerPopular(results: HubDataset[] = []): Promise<void> {
    await settle();
    backend.expectOne((request) => request.url === HUB).flush(page(results));
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        DatasetsStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: (names: readonly string[]) => names.includes('trainers') } },
      ],
    });
    store = TestBed.inject(DatasetsStore);
    backend = TestBed.inject(HttpTestingController);
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
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
    request.flush(page([dataset('1')], 60));
    await loading;

    expect(store.pageIndex()).toBe(1);
    expect(store.page().count).toBe(60);
    expect(store.canWrite()).toBe(true);
  });

  describe('searching HuggingFace', () => {
    it('lists popular datasets without parameters', async () => {
      await settle();
      const request = backend.expectOne((r) => r.url === HUB);
      expect(request.request.params.keys()).toEqual([]);
      request.flush(page([hubDataset('tatsu-lab/alpaca')]));
      await settle();

      expect(store.hubResults().map((result) => result.repo_id)).toEqual(['tatsu-lab/alpaca']);
      expect(store.hubLoading()).toBe(false);
    });

    it('sends the trimmed words', async () => {
      await answerPopular();

      store.search('  arabic chat ');
      await settle();
      const request = backend.expectOne((r) => r.url === HUB);
      expect(request.request.params.get('search')).toBe('arabic chat');
      request.flush(page([hubDataset('org/arabic-chat')]));
      await settle();

      expect(store.hubQuery()).toBe('arabic chat');
      expect(store.hubResults()).toHaveLength(1);
    });

    it('keeps the reason and tries again', async () => {
      await settle();
      backend
        .expectOne((r) => r.url === HUB)
        .flush({ error: { code: 'hf_unreachable', message: 'Down.' } }, { status: 503, statusText: 'Unavailable' });
      await settle();

      expect(store.hubError()?.code).toBe('hf_unreachable');

      store.searchAgain();
      await settle();
      backend.expectOne((r) => r.url === HUB).flush(page([hubDataset('tatsu-lab/alpaca')]));
      await settle();

      expect(store.hubError()).toBeNull();
    });
  });

  describe('inspecting a dataset', () => {
    it('sends the split and the chosen columns, then forgets it', async () => {
      await answerPopular();
      expect(store.inspection()).toBeNull();

      store.inspect({
        repo: 'tatsu-lab/alpaca',
        config: 'default',
        split: 'train',
        columns: { prompt: 'instruction', reply: 'output', thinking: '' },
      });
      await settle();
      const request = backend.expectOne((r) => r.url === INSPECT);
      expect(request.request.params.get('repo')).toBe('tatsu-lab/alpaca');
      expect(request.request.params.get('split')).toBe('train');
      expect(request.request.params.get('prompt')).toBe('instruction');
      expect(request.request.params.get('reply')).toBe('output');
      expect(store.inspecting()).toBe(true);
      request.flush(inspection('tatsu-lab/alpaca'));
      await settle();

      expect(store.inspection()?.detected).toBe('instruction');

      store.stopInspecting();
      await settle();
      expect(store.inspection()).toBeNull();
    });

    it('reports a dataset that needs a token, in the reader\'s language', async () => {
      await answerPopular();

      store.inspect({ repo: 'meta/gated' });
      await settle();
      const request = backend.expectOne((r) => r.url === INSPECT);
      expect(request.request.params.has('prompt')).toBe(false);
      request.flush(
        { error: { code: 'hub_dataset_gated', message: 'raw' } },
        { status: 400, statusText: 'Bad Request' },
      );
      await settle();

      expect(store.inspectionError()?.message).toBe(en.errors.hub_dataset_gated);
    });
  });

  it('imports, then reloads the first page and the search', async () => {
    await answerPopular([hubDataset('tatsu-lab/alpaca')]);

    const importing = store.startImport({
      repo_id: 'tatsu-lab/alpaca',
      config: 'default',
      split: 'train',
      row_limit: 200,
      mapping: MAPPING,
    });
    expect(store.importing()).toBe(true);
    const request = backend.expectOne((r) => r.url === LIBRARY && r.method === 'POST');
    expect(request.request.body).toEqual({
      repo_id: 'tatsu-lab/alpaca',
      config: 'default',
      split: 'train',
      row_limit: 200,
      mapping: MAPPING,
    });
    request.flush(dataset('1', { status: 'queued' }), { status: 202, statusText: 'Accepted' });
    await vi.advanceTimersByTimeAsync(0);
    library().flush(page([dataset('1', { status: 'queued' })]));
    await settle();
    backend.expectOne((r) => r.url === HUB).flush(page([{ ...hubDataset('tatsu-lab/alpaca'), in_library: true }]));
    await settle();

    expect(await importing).toBeNull();
    expect(store.importing()).toBe(false);
    expect(store.busy()).toBe(true);
    expect(store.hubResults()[0].in_library).toBe(true);
  });

  describe('uploading a file', () => {
    it('sends the file with its name and reports progress', async () => {
      await answerPopular();
      const file = new File(['{"text": "hello"}\n'], 'lines.jsonl');

      const uploading = store.upload(file, 'Greetings');
      expect(store.uploading()).toBe(true);
      const request = backend.expectOne(UPLOAD);
      const body = request.request.body as FormData;
      expect((body.get('file') as File).name).toBe('lines.jsonl');
      expect(body.get('name')).toBe('Greetings');
      expect(request.request.reportProgress).toBe(true);

      request.event({ type: HttpEventType.UploadProgress, loaded: 50, total: 200 });
      expect(store.uploadProgress()).toBe(25);
      request.flush(dataset('1', { source: 'upload', file_name: 'lines.jsonl' }), {
        status: 201,
        statusText: 'Created',
      });
      await vi.advanceTimersByTimeAsync(0);
      library().flush(page([dataset('1', { source: 'upload' })]));

      expect(await uploading).toBeNull();
      expect(store.uploading()).toBe(false);
      expect(store.page().results[0].source).toBe('upload');
    });

    it('hands back a refusal in the reader\'s language', async () => {
      const uploading = store.upload(new File(['x'], 'rows.parquet'));
      backend
        .expectOne(UPLOAD)
        .flush({ error: { code: 'unsupported_file', message: 'raw' } }, { status: 400, statusText: 'Bad Request' });

      const failure = await uploading;
      expect(failure?.code).toBe('unsupported_file');
      expect(failure?.message).toBe(en.errors.unsupported_file);
      expect(store.uploading()).toBe(false);
    });
  });

  describe('while an import runs', () => {
    beforeEach(async () => {
      await answerPopular();
    });

    it('refreshes every two seconds and stops once nothing is importing', async () => {
      const watching = store.watchImports().subscribe();
      await loadLibrary([dataset('1', { status: 'importing', rows: 100 })]);
      expect(store.busy()).toBe(true);

      await vi.advanceTimersByTimeAsync(1999);
      backend.expectNone((request) => request.url === LIBRARY);

      await vi.advanceTimersByTimeAsync(1);
      library().flush(page([dataset('1', { status: 'importing', rows: 4_000 })]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.page().results[0].rows).toBe(4_000);

      await vi.advanceTimersByTimeAsync(2000);
      library().flush(page([dataset('1')]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.busy()).toBe(false);

      await vi.advanceTimersByTimeAsync(10_000);
      backend.expectNone((request) => request.url === LIBRARY);
      watching.unsubscribe();
    });

    it('keeps the last list when a background refresh fails', async () => {
      const watching = store.watchImports().subscribe();
      await loadLibrary([dataset('1', { status: 'queued' })]);

      await vi.advanceTimersByTimeAsync(2000);
      library().flush({}, { status: 500, statusText: 'Server Error' });
      await vi.advanceTimersByTimeAsync(0);

      expect(store.page().results).toHaveLength(1);
      expect(store.error()).toBeNull();
      watching.unsubscribe();
    });

    it('cancels one row and leaves the others', async () => {
      await loadLibrary([dataset('1', { status: 'importing' }), dataset('2')]);

      const cancelling = store.cancel(dataset('1'));
      backend.expectOne('/api/datasets/1/cancel/').flush(dataset('1', { status: 'cancelled' }));

      expect(await cancelling).toBe(true);
      expect(store.page().results.map((row) => row.status)).toEqual(['cancelled', 'ready']);
      expect(store.working()).toEqual([]);
    });
  });

  it('removes a dataset and steps back a page when its page empties', async () => {
    await answerPopular();
    const loading = store.load(1, 1);
    library().flush(page([dataset('2')], 2));
    await loading;

    const removing = store.remove(dataset('2'));
    backend.expectOne((request) => request.method === 'DELETE').flush(null, { status: 204, statusText: 'No Content' });
    await vi.advanceTimersByTimeAsync(0);
    const reload = library();
    expect(reload.request.params.get('page')).toBe('1');
    reload.flush(page([dataset('1')], 1));
    await settle();
    backend.expectOne((request) => request.url === HUB).flush(page([]));

    expect(await removing).toBe(true);
    expect(store.pageIndex()).toBe(0);
  });

  it('keeps a refused removal as an error', async () => {
    await loadLibrary([dataset('1')]);

    const removing = store.remove(dataset('1'));
    backend
      .expectOne((request) => request.method === 'DELETE')
      .flush({ error: { code: 'not_found', message: 'Gone.' } }, { status: 404, statusText: 'Not Found' });

    expect(await removing).toBe(false);
    expect(store.error()?.message).toBe('Gone.');
    expect(store.page().results).toHaveLength(1);
  });

  it('opens a dataset and pages through its rows', async () => {
    await answerPopular();
    const opening = store.open('1');
    backend.expectOne('/api/datasets/1/').flush(dataset('1', { rows: 25 }));
    await vi.advanceTimersByTimeAsync(0);
    const first = backend.expectOne((request) => request.url === '/api/datasets/1/rows/');
    expect(first.request.params.get('page_size')).toBe('10');
    first.flush(page([conversation(0)], 25));
    await opening;

    expect(store.rows().count).toBe(25);

    const turning = store.loadRows(2, 10);
    const third = backend.expectOne((request) => request.url === '/api/datasets/1/rows/');
    expect(third.request.params.get('page')).toBe('3');
    third.flush(page([conversation(20)], 25));
    await turning;

    expect(store.rowsIndex()).toBe(2);
    expect(store.rows().results[0].index).toBe(20);
  });

  it('waits for an opened import to finish before reading its rows', async () => {
    await answerPopular();
    const watching = store.watchOpened().subscribe();
    const opening = store.open('1');
    backend.expectOne('/api/datasets/1/').flush(dataset('1', { status: 'importing', rows: 10 }));
    await opening;
    backend.expectNone((request) => request.url === '/api/datasets/1/rows/');

    await vi.advanceTimersByTimeAsync(2000);
    backend.expectOne('/api/datasets/1/').flush(dataset('1', { rows: 40 }));
    await vi.advanceTimersByTimeAsync(0);
    backend.expectOne((request) => request.url === '/api/datasets/1/rows/').flush(page([conversation(0)], 40));
    await vi.advanceTimersByTimeAsync(0);

    expect(store.openedBusy()).toBe(false);
    expect(store.rows().count).toBe(40);
    await vi.advanceTimersByTimeAsync(10_000);
    backend.expectNone('/api/datasets/1/');
    watching.unsubscribe();
  });
});
