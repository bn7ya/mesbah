import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Metric, Run, RunStatus } from '../data/training.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { RunStore } from './run.store';

const RUN = '/api/training/r1/';
const METRICS = '/api/training/r1/metrics/';

function run(status: RunStatus, overrides: Partial<Run> = {}): Run {
  return {
    id: 'r1',
    project: 'p1',
    name: 'Friendlier',
    notes: '',
    starts_from: { id: 'v0', name: 'base', number: 0 },
    version: null,
    use_corrections: true,
    datasets: [],
    hyperparams: {},
    activate_when_done: true,
    status,
    stage: status === 'training' ? 'training' : '',
    examples: 4,
    skipped: 0,
    tokens: 900,
    step: 0,
    total_steps: 30,
    epoch: null,
    loss: null,
    max_seq_len: null,
    gpu_indices: [],
    error_code: '',
    error_detail: '',
    cancel_requested: false,
    started_at: '2026-10-18T10:00:00Z',
    finished_at: null,
    created_at: '2026-10-18T09:59:00Z',
    created_by: 'tariq',
    ...overrides,
  };
}

function point(step: number, loss: number): Metric {
  return { step, epoch: step / 10, loss, learning_rate: 0.005, grad_norm: 1.5 };
}

function page<T>(rows: T[], overrides: Partial<Page<T>> = {}): Page<T> {
  return { count: rows.length, next: null, previous: null, results: rows, ...overrides };
}

describe('RunStore', () => {
  let store: RunStore;
  let backend: HttpTestingController;
  let asked: (readonly string[])[] = [];

  function runRequest(): TestRequest {
    return backend.expectOne((request) => request.url === RUN && request.method === 'GET');
  }

  function metricsRequest(): TestRequest {
    return backend.expectOne((request) => request.url === METRICS);
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function answer(status: RunStatus, step: number, points: Metric[], overrides: Partial<Run> = {}): Promise<void> {
    runRequest().flush(run(status, { step, ...overrides }));
    await vi.advanceTimersByTimeAsync(0);
    metricsRequest().flush(page(points));
    await vi.advanceTimersByTimeAsync(0);
  }

  async function open(status: RunStatus = 'training', step = 3, points: Metric[] = [point(1, 3), point(2, 2.5), point(3, 2.1)]): Promise<void> {
    store.open('r1');
    await settle();
    await answer(status, step, points);
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-18T10:01:00Z'));
    asked = [];
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        RunStore,
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
    store = TestBed.inject(RunStore);
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

  it('loads the run and every point so far', async () => {
    store.open('r1');
    await settle();
    expect(store.loading()).toBe(true);
    runRequest().flush(run('training', { step: 3 }));
    await vi.advanceTimersByTimeAsync(0);
    const request = metricsRequest();
    expect(request.request.params.get('after_step')).toBe('0');
    expect(request.request.params.get('page_size')).toBe('200');
    request.flush(page([point(1, 3), point(2, 2.5), point(3, 2.1)]));
    await vi.advanceTimersByTimeAsync(0);

    expect(store.loading()).toBe(false);
    expect(store.run()?.status).toBe('training');
    expect(store.points().map((p) => p.step)).toEqual([1, 2, 3]);
    expect(store.progress()).toBe(10);
  });

  it('refreshes every two seconds and appends the points after the last step', async () => {
    const watching = store.watch().subscribe();
    await open();

    await vi.advanceTimersByTimeAsync(1999);
    backend.expectNone((request) => request.url === RUN);

    await vi.advanceTimersByTimeAsync(1);
    runRequest().flush(run('training', { step: 5 }));
    await vi.advanceTimersByTimeAsync(0);
    const request = metricsRequest();
    expect(request.request.params.get('after_step')).toBe('3');
    request.flush(page([point(4, 1.9), point(5, 1.8)]));
    await vi.advanceTimersByTimeAsync(0);

    expect(store.points().map((p) => p.step)).toEqual([1, 2, 3, 4, 5]);
    expect(store.run()?.step).toBe(5);
    watching.unsubscribe();
  });

  it('never repeats a step it already has', async () => {
    const watching = store.watch().subscribe();
    await open();

    await vi.advanceTimersByTimeAsync(2000);
    await answer('training', 4, [point(3, 2.1), point(4, 2)]);

    expect(store.points().map((p) => p.step)).toEqual([1, 2, 3, 4]);
    watching.unsubscribe();
  });

  it('follows the metric pages', async () => {
    store.open('r1');
    await settle();
    runRequest().flush(run('training', { step: 4 }));
    await vi.advanceTimersByTimeAsync(0);
    metricsRequest().flush(page([point(1, 3), point(2, 2.5)], { count: 4, next: 'http://x/?page=2' }));
    await vi.advanceTimersByTimeAsync(0);
    const second = metricsRequest();
    expect(second.request.params.get('page')).toBe('2');
    second.flush(page([point(3, 2.1), point(4, 2)], { count: 4 }));
    await vi.advanceTimersByTimeAsync(0);

    expect(store.points().map((p) => p.step)).toEqual([1, 2, 3, 4]);
  });

  it('stops polling at a terminal state, after one last look at the points', async () => {
    const watching = store.watch().subscribe();
    await open();

    await vi.advanceTimersByTimeAsync(2000);
    await answer('completed', 30, [point(4, 1.9), point(30, 0.8)], { finished_at: '2026-10-18T10:01:30Z', loss: 0.8 });
    expect(store.finished()).toBe(true);
    expect(store.points().at(-1)?.step).toBe(30);

    await vi.advanceTimersByTimeAsync(20_000);
    backend.expectNone((request) => request.url === RUN);
    watching.unsubscribe();
  });

  it('does not poll a run that is already over', async () => {
    const watching = store.watch().subscribe();
    await open('failed', 0, []);

    await vi.advanceTimersByTimeAsync(20_000);
    backend.expectNone((request) => request.url === RUN);
    watching.unsubscribe();
  });

  it('does not poll once the page stops watching', async () => {
    const watching = store.watch().subscribe();
    await open();
    watching.unsubscribe();

    await vi.advanceTimersByTimeAsync(20_000);
    backend.expectNone((request) => request.url === RUN);
  });

  it('keeps what it has when a background poll fails', async () => {
    const watching = store.watch().subscribe();
    await open();

    await vi.advanceTimersByTimeAsync(2000);
    runRequest().flush({}, { status: 500, statusText: 'Server Error' });
    await vi.advanceTimersByTimeAsync(0);

    expect(store.run()?.step).toBe(3);
    expect(store.points()).toHaveLength(3);
    expect(store.error()).toBeNull();
    watching.unsubscribe();
  });

  it('estimates the time left from the recent step rate', async () => {
    const watching = store.watch().subscribe();
    await open('training', 4, [point(4, 2)]);
    expect(store.remainingSeconds()).toBeNull();

    await vi.advanceTimersByTimeAsync(2000);
    await answer('training', 6, [point(5, 1.9), point(6, 1.8)]);
    await vi.advanceTimersByTimeAsync(2000);
    await answer('training', 8, [point(7, 1.7), point(8, 1.6)]);

    expect(store.remainingSeconds()).toBe(22);
    watching.unsubscribe();
  });

  it('counts the time since it started, and stops counting when it ends', async () => {
    const watching = store.watch().subscribe();
    await open();
    expect(store.elapsedSeconds()).toBe(60);

    await vi.advanceTimersByTimeAsync(1000);
    expect(store.elapsedSeconds()).toBe(61);

    await vi.advanceTimersByTimeAsync(1000);
    await answer('completed', 30, [point(30, 0.8)], { finished_at: '2026-10-18T10:01:30Z' });
    expect(store.elapsedSeconds()).toBe(90);
    watching.unsubscribe();
  });

  it('stops a run and waits for the next step to end it', async () => {
    await open();

    const stopping = store.stop();
    expect(store.stopping()).toBe(true);
    const request = backend.expectOne((r) => r.url === '/api/training/r1/cancel/');
    expect(request.request.method).toBe('POST');
    request.flush(run('training', { step: 3 }));

    expect(await stopping).toBe(true);
    expect(store.stopping()).toBe(true);
    expect(store.canStop()).toBe(true);
  });

  it('shows a stop asked for elsewhere', async () => {
    store.open('r1');
    await settle();
    await answer('training', 3, [], { cancel_requested: true });

    expect(store.stopping()).toBe(true);
  });

  it('reports a refused stop', async () => {
    await open();

    const stopping = store.stop();
    backend
      .expectOne((r) => r.url === '/api/training/r1/cancel/')
      .flush({ error: { code: 'invalid', message: 'No.' } }, { status: 400, statusText: 'Bad Request' });

    expect(await stopping).toBe(false);
    expect(store.stopping()).toBe(false);
    expect(store.stopError()?.code).toBe('invalid');
  });

  it('says the run cannot be found', async () => {
    store.open('r1');
    await settle();
    runRequest().flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });
    await vi.advanceTimersByTimeAsync(0);

    expect(store.error()?.code).toBe('not_found');
    expect(store.run()).toBeNull();
    expect(store.loading()).toBe(false);
  });

  it('asks for the size of the new version once the run is completed', async () => {
    store.open('r1');
    await settle();
    runRequest().flush(run('completed', { step: 30, version: { id: 'v7', name: 'Friendlier', number: 7 } }));
    await vi.advanceTimersByTimeAsync(0);
    metricsRequest().flush(page([point(30, 0.8)]));
    await settle();
    backend.expectOne('/api/versions/v7/').flush({ size_bytes: 84_000_000, full_size_bytes: 16_000_000_000 });
    await settle();

    expect(store.size()).toEqual({ sizeBytes: 84_000_000, fullSizeBytes: 16_000_000_000 });
  });

  it('starts over when it is opened on another run', async () => {
    await open();

    store.open('r2');
    expect(store.run()).toBeNull();
    expect(store.points()).toEqual([]);
    await settle();
    backend.expectOne('/api/training/r2/').flush(run('queued', { id: 'r2', started_at: null }));
    await vi.advanceTimersByTimeAsync(0);
    backend.expectOne((request) => request.url === '/api/training/r2/metrics/').flush(page([]));
    await vi.advanceTimersByTimeAsync(0);

    expect(store.run()?.id).toBe('r2');
  });

  it('lets trainers and above stop, and no one below', async () => {
    await open();

    expect(store.canStop()).toBe(true);
    expect(asked).toContainEqual(['trainers', 'admins']);
  });

  it('does not offer to stop a finished run', async () => {
    await open('completed', 30, [point(30, 0.8)]);

    expect(store.canStop()).toBe(false);
  });
});
