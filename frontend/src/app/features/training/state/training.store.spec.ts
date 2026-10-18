import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import { FALLBACK_SETTINGS, type Draft, type Example, type Plan, type Run, type RunStatus } from '../data/training.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { TrainingStore } from './training.store';

const RUNS = '/api/training/';
const PLAN = '/api/training/plan/';
const EXAMPLES = '/api/training/examples/';
const VERSIONS = '/api/versions/';
const DATASETS = '/api/datasets/';

function run(id: string, status: RunStatus, overrides: Partial<Run> = {}): Run {
  return {
    id,
    project: 'p1',
    name: `Run ${id}`,
    notes: '',
    starts_from: { id: 'v1', name: 'base', number: 0 },
    version: null,
    use_corrections: true,
    datasets: [],
    hyperparams: {},
    activate_when_done: true,
    status,
    stage: '',
    examples: 4,
    skipped: 0,
    tokens: 900,
    step: 0,
    total_steps: 0,
    epoch: null,
    loss: null,
    max_seq_len: null,
    gpu_indices: [],
    error_code: '',
    error_detail: '',
    cancel_requested: false,
    started_at: null,
    finished_at: null,
    created_at: '2026-10-18T10:00:00Z',
    created_by: 'tariq',
    ...overrides,
  };
}

function page<T>(rows: T[], overrides: Partial<Page<T>> = {}): Page<T> {
  return { count: rows.length, next: null, previous: null, results: rows, ...overrides };
}

const PLAN_BODY: Plan = {
  hyperparams: { ...FALLBACK_SETTINGS, epochs: 2 },
  corrections: 7,
  fit: { verdict: 'cpu_only', required_bytes: 4_000_000_000, available_bytes: 0 },
  gpu_indices: [],
};

const DRAFT: Draft = {
  startsFrom: 'v1',
  name: ' Friendlier ',
  useCorrections: true,
  datasets: [],
  activateWhenDone: true,
  settings: { ...FALLBACK_SETTINGS, epochs: 3, max_steps: null },
};

function dataset(id: string, status: string, rows = 100): Record<string, unknown> {
  return { id, name: `Set ${id}`, status, rows, format: 'messages', source: 'hub', repo_id: `org/${id}`, has_thinking: false };
}

const DATASET_ROWS = [dataset('d1', 'ready', 1200), dataset('d2', 'importing'), dataset('d3', 'failed'), dataset('d4', 'ready', 40)];

const VERSION_ROWS = [
  { id: 'v0', number: 0, name: 'base', kind: 'base', is_active: false, size_bytes: 0, full_size_bytes: 1000 },
  { id: 'v1', number: 1, name: 'First', kind: 'lora', is_active: true, size_bytes: 10, full_size_bytes: 1000 },
];

describe('TrainingStore', () => {
  let store: TrainingStore;
  let backend: HttpTestingController;
  let asked: (readonly string[])[] = [];

  function runsRequest(): TestRequest {
    return backend.expectOne((request) => request.url === RUNS && request.method === 'GET');
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  function answerSetup(): void {
    backend.expectOne((request) => request.url === PLAN).flush(PLAN_BODY);
    backend.expectOne((request) => request.url === VERSIONS).flush(page(VERSION_ROWS));
    backend.expectOne((request) => request.url === DATASETS).flush(page(DATASET_ROWS));
  }

  async function open(rows: Run[] = []): Promise<void> {
    store.open('p1');
    await settle();
    answerSetup();
    runsRequest().flush(page(rows));
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    asked = [];
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        TrainingStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        {
          provide: AuthStore,
          useValue: {
            hasAnyGroup: (names: readonly string[]) => {
              asked.push(names);
              return true;
            },
          },
        },
      ],
    });
    store = TestBed.inject(TrainingStore);
    backend = TestBed.inject(HttpTestingController);
    TestBed.inject(LocaleStore).register({ en, ar });
    TestBed.inject(LocaleStore).setLocale('en');
  });

  afterEach(() => {
    try {
      backend.verify();
    } finally {
      TestBed.resetTestingModule();
      vi.useRealTimers();
    }
  });

  it('asks for the plan, the versions and the runs of the open project', async () => {
    store.open('p1');
    await settle();

    const plan = backend.expectOne((request) => request.url === PLAN);
    expect(plan.request.params.get('project')).toBe('p1');
    const versions = backend.expectOne((request) => request.url === VERSIONS);
    expect(versions.request.params.get('project')).toBe('p1');
    const runs = runsRequest();
    expect(runs.request.params.get('project')).toBe('p1');
    expect(runs.request.params.get('page')).toBe('1');
    plan.flush(PLAN_BODY);
    versions.flush(page(VERSION_ROWS));
    backend.expectOne((request) => request.url === DATASETS).flush(page(DATASET_ROWS));
    runs.flush(page([run('r1', 'completed')]));
    await settle();

    expect(store.plan()?.corrections).toBe(7);
    expect(store.plan()?.fit.verdict).toBe('cpu_only');
    expect(store.versions().map((version) => [version.id, version.isActive])).toEqual([
      ['v0', false],
      ['v1', true],
    ]);
    expect(store.runs().results.map((row) => row.id)).toEqual(['r1']);
  });

  it('offers only the library datasets that are ready', async () => {
    await open();

    expect(store.datasets()).toEqual([
      { id: 'd1', name: 'Set d1', rows: 1200, hasThinking: false },
      { id: 'd4', name: 'Set d4', rows: 40, hasThinking: false },
    ]);
  });

  it('follows the dataset pages until every ready dataset is here', async () => {
    store.open('p1');
    await settle();
    backend.expectOne((request) => request.url === PLAN).flush(PLAN_BODY);
    backend.expectOne((request) => request.url === VERSIONS).flush(page(VERSION_ROWS));
    runsRequest().flush(page([]));
    backend
      .expectOne((request) => request.url === DATASETS)
      .flush(page([dataset('d1', 'ready')], { count: 2, next: 'http://x/?page=2' }));
    await settle();
    const second = backend.expectOne((request) => request.url === DATASETS);
    expect(second.request.params.get('page')).toBe('2');
    second.flush(page([dataset('d2', 'ready')], { count: 2 }));
    await settle();

    expect(store.datasets().map((item) => item.id)).toEqual(['d1', 'd2']);
  });

  it('reports a library that could not load', async () => {
    store.open('p1');
    await settle();
    backend.expectOne((request) => request.url === PLAN).flush(PLAN_BODY);
    backend.expectOne((request) => request.url === VERSIONS).flush(page(VERSION_ROWS));
    runsRequest().flush(page([]));
    backend
      .expectOne((request) => request.url === DATASETS)
      .flush({ error: { code: 'unknown', message: 'x' } }, { status: 500, statusText: 'Server Error' });
    await settle();

    expect(store.datasetsError()).not.toBeNull();
    expect(store.datasets()).toEqual([]);
  });

  it('follows the version pages until every version is here', async () => {
    store.open('p1');
    await settle();
    backend.expectOne((request) => request.url === PLAN).flush(PLAN_BODY);
    backend.expectOne((request) => request.url === DATASETS).flush(page([]));
    runsRequest().flush(page([]));
    backend
      .expectOne((request) => request.url === VERSIONS)
      .flush(page([VERSION_ROWS[0]], { count: 2, next: 'http://x/?page=2' }));
    await settle();
    const second = backend.expectOne((request) => request.url === VERSIONS);
    expect(second.request.params.get('page')).toBe('2');
    second.flush(page([VERSION_ROWS[1]], { count: 2 }));
    await settle();

    expect(store.versions().map((version) => version.id)).toEqual(['v0', 'v1']);
  });

  it('sends the draft as a run, leaving out an empty step limit and trimming the name', async () => {
    await open();

    const starting = store.start(DRAFT);
    expect(store.starting()).toBe(true);
    const request = backend.expectOne((r) => r.url === RUNS && r.method === 'POST');
    expect(request.request.body).toEqual({
      project: 'p1',
      starts_from: 'v1',
      name: 'Friendlier',
      use_corrections: true,
      datasets: [],
      activate_when_done: true,
      hyperparams: {
        epochs: 3,
        learning_rate: 2e-4,
        lora_rank: 16,
        lora_alpha: 32,
        lora_dropout: 0,
        use_rslora: false,
        train_biases: false,
        max_seq_len: 2048,
        batch_size: 1,
        grad_accum: 8,
        quantize_4bit: false,
        gradient_checkpointing: true,
      },
    });
    request.flush(run('r9', 'queued'));

    expect(await starting).toEqual({ run: run('r9', 'queued') });
    expect(store.starting()).toBe(false);
  });

  it('sends the chosen datasets with their row limits, and learns from them alone when asked', async () => {
    await open();

    const starting = store.start({
      ...DRAFT,
      useCorrections: false,
      datasets: [
        { id: 'd1', maxRows: 500 },
        { id: 'd4', maxRows: null },
      ],
    });
    const request = backend.expectOne((r) => r.url === RUNS && r.method === 'POST');
    const body = request.request.body as { use_corrections: boolean; datasets: unknown[] };
    expect(body.use_corrections).toBe(false);
    expect(body.datasets).toEqual([
      { id: 'd1', max_rows: 500 },
      { id: 'd4', max_rows: null },
    ]);
    request.flush(run('r9', 'queued'));
    await starting;
  });

  it('says in words that a chosen dataset is not ready', async () => {
    await open();

    const starting = store.start({ ...DRAFT, datasets: [{ id: 'd2', maxRows: null }] });
    backend
      .expectOne((r) => r.url === RUNS && r.method === 'POST')
      .flush({ error: { code: 'dataset_not_ready', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

    const result = await starting;
    expect('error' in result && result.error.message).toBe(en.errors.dataset_not_ready);
  });

  it('sends a step limit when one is set', async () => {
    await open();

    const starting = store.start({ ...DRAFT, settings: { ...DRAFT.settings, max_steps: 30 } });
    const request = backend.expectOne((r) => r.url === RUNS && r.method === 'POST');
    expect((request.request.body as { hyperparams: { max_steps: number } }).hyperparams.max_steps).toBe(30);
    request.flush(run('r9', 'queued'));
    await starting;
  });

  it('says in words why a run has nothing to learn from', async () => {
    await open();

    const starting = store.start(DRAFT);
    backend
      .expectOne((r) => r.url === RUNS && r.method === 'POST')
      .flush({ error: { code: 'nothing_to_learn', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

    const result = await starting;
    expect('error' in result && result.error.code).toBe('nothing_to_learn');
    expect('error' in result && result.error.message).toBe(en.errors.nothing_to_learn);
    expect(store.starting()).toBe(false);
  });

  describe('while a run goes', () => {
    it('refreshes the runs every three seconds and stops once all are finished', async () => {
      const watching = store.watchRuns().subscribe();
      await open([run('r1', 'training', { step: 2, total_steps: 30 })]);
      expect(store.unfinished()).toBe(true);

      await vi.advanceTimersByTimeAsync(2999);
      backend.expectNone((request) => request.url === RUNS);

      await vi.advanceTimersByTimeAsync(1);
      runsRequest().flush(page([run('r1', 'training', { step: 9, total_steps: 30 })]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.runs().results[0].step).toBe(9);

      await vi.advanceTimersByTimeAsync(3000);
      runsRequest().flush(page([run('r1', 'completed', { step: 30, total_steps: 30 })]));
      await vi.advanceTimersByTimeAsync(0);
      expect(store.unfinished()).toBe(false);
      answerSetup();

      await vi.advanceTimersByTimeAsync(20_000);
      backend.expectNone((request) => request.url === RUNS);
      watching.unsubscribe();
    });

    it('does not poll when every run is already finished', async () => {
      const watching = store.watchRuns().subscribe();
      await open([run('r1', 'completed'), run('r2', 'failed'), run('r3', 'cancelled')]);

      await vi.advanceTimersByTimeAsync(20_000);
      backend.expectNone((request) => request.url === RUNS);
      watching.unsubscribe();
    });

    it('does not poll once the page stops watching', async () => {
      const watching = store.watchRuns().subscribe();
      await open([run('r1', 'queued')]);
      watching.unsubscribe();

      await vi.advanceTimersByTimeAsync(20_000);
      backend.expectNone((request) => request.url === RUNS);
    });

    it('keeps the last list when a background refresh fails', async () => {
      const watching = store.watchRuns().subscribe();
      await open([run('r1', 'training')]);

      await vi.advanceTimersByTimeAsync(3000);
      runsRequest().flush({}, { status: 500, statusText: 'Server Error' });
      await vi.advanceTimersByTimeAsync(0);

      expect(store.runs().results).toHaveLength(1);
      expect(store.runsError()).toBeNull();
      watching.unsubscribe();
    });
  });

  it('stops a run and remembers it was asked to stop', async () => {
    await open([run('r1', 'training')]);

    const stopping = store.stop(run('r1', 'training'));
    expect(store.working()).toEqual(['r1']);
    const request = backend.expectOne((r) => r.url === '/api/training/r1/cancel/');
    expect(request.request.method).toBe('POST');
    request.flush(run('r1', 'training'));

    expect(await stopping).toBe(true);
    expect(store.stopping()).toEqual(['r1']);
    expect(store.working()).toEqual([]);
  });

  it('shows a waiting run as stopped at once', async () => {
    await open([run('r1', 'queued')]);

    const stopping = store.stop(run('r1', 'queued'));
    backend.expectOne((r) => r.url === '/api/training/r1/cancel/').flush(run('r1', 'cancelled'));

    expect(await stopping).toBe(true);
    expect(store.runs().results[0].status).toBe('cancelled');
    expect(store.stopping()).toEqual([]);
    expect(store.unfinished()).toBe(false);
  });

  it('removes a finished run and loads the list again', async () => {
    await open([run('r1', 'completed'), run('r2', 'failed')]);

    const removing = store.remove(run('r1', 'completed'));
    const request = backend.expectOne((r) => r.url === '/api/training/r1/' && r.method === 'DELETE');
    request.flush(null, { status: 204, statusText: 'No Content' });
    await vi.advanceTimersByTimeAsync(0);
    runsRequest().flush(page([run('r2', 'failed')]));

    expect(await removing).toBe(true);
    expect(store.runs().results.map((row) => row.id)).toEqual(['r2']);
  });

  it('says in words why a run still going cannot be removed', async () => {
    await open([run('r1', 'training')]);

    const removing = store.remove(run('r1', 'training'));
    backend
      .expectOne((r) => r.method === 'DELETE')
      .flush({ error: { code: 'run_still_going', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

    expect(await removing).toBe(false);
    expect(store.error()?.message).toBe(en.errors.run_still_going);
    expect(store.runs().results).toHaveLength(1);
  });

  it('reports runs that could not load', async () => {
    store.open('p1');
    await settle();
    answerSetup();
    runsRequest().flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });
    await settle();

    expect(store.runsError()?.code).toBe('not_found');
    expect(store.runsLoading()).toBe(false);
  });

  it('loads a page of examples', async () => {
    await open();

    const loading = store.loadExamples(1, 5);
    const request = backend.expectOne((r) => r.url === EXAMPLES);
    expect(request.request.params.get('project')).toBe('p1');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('5');
    const example: Example = {
      id: 'm1',
      conversation: { id: 'c1', title: 'Shipping' },
      messages: [
        { role: 'user', content: 'How long?' },
        { role: 'assistant', content: 'Three days.' },
      ],
      corrected: true,
      thinking_corrected: false,
      approved_by: 'rana',
      updated_at: '2026-10-18T10:00:00Z',
    };
    request.flush(page([example], { count: 6 }));
    await loading;

    expect(store.examples().results).toEqual([example]);
    expect(store.examplesPageIndex()).toBe(1);
    expect(store.examplesLoading()).toBe(false);
  });

  it('lets trainers and above start training, and no one below', () => {
    expect(store.canWrite()).toBe(true);
    expect(asked).toEqual([['trainers', 'admins']]);
  });
});
