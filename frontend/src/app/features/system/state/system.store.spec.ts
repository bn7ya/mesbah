import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { SystemOverview } from '../data/system.types';
import { SystemStore } from './system.store';

const GIB = 1024 ** 3;

function overview(overrides: Partial<SystemOverview> = {}): SystemOverview {
  return {
    version: '0.1.0',
    machine: {
      gpus: [
        { index: 0, name: 'RTX 5080', memory_bytes: 16 * GIB, compute_capability: '12.0' },
        { index: 1, name: 'RTX 3060', memory_bytes: 12 * GIB, compute_capability: '8.6' },
      ],
      driver: '595.71.05',
      ram_bytes: 64 * GIB,
      cpu_count: 16,
      system: 'Linux 6.18',
      python: '3.13.16',
    },
    selected_gpus: [0],
    gpu_choice: 'automatic',
    usable_vram_bytes: 16 * GIB,
    storage: { path: '/data', free_bytes: 100 * GIB, total_bytes: 500 * GIB },
    parts: [
      { name: 'torch', purpose: 'training', version: '2.14.1+cpu', cuda: false },
      { name: 'transformers', purpose: 'training', version: '5.20.1', cuda: null },
      { name: 'peft', purpose: 'training', version: '0.21.2', cuda: null },
      { name: 'trl', purpose: 'training', version: null, cuda: null },
    ],
    huggingface: { configured: false, hint: '', account: '' },
    ...overrides,
  };
}

describe('SystemStore', () => {
  let store: SystemStore;
  let backend: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SystemStore, provideHttpClient(), provideHttpClientTesting()],
    });
    store = TestBed.inject(SystemStore);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    backend.verify();
    TestBed.resetTestingModule();
  });

  it('loads the overview and names the GPUs in use', async () => {
    const loading = store.load();
    backend.expectOne('/api/system/').flush(overview());
    await loading;

    expect(store.selectedGpus().map((gpu) => gpu.name)).toEqual(['RTX 5080']);
  });

  it('is not ready to train while a training part is missing', async () => {
    const loading = store.load();
    backend.expectOne('/api/system/').flush(overview());
    await loading;

    expect(store.trainingReady()).toBe(false);
  });

  it('warns when a GPU is present but the training parts are a CPU build', async () => {
    const loading = store.load();
    backend.expectOne('/api/system/').flush(overview());
    await loading;

    expect(store.torchWithoutCuda()).toBe(true);
  });

  it('sends the chosen GPUs and keeps the answer', async () => {
    const saving = store.selectGpus([0, 1]);
    const request = backend.expectOne('/api/system/gpus/');
    expect(request.request.body).toEqual({ gpus: [0, 1] });
    request.flush(overview({ selected_gpus: [0, 1], gpu_choice: 'chosen', usable_vram_bytes: 28 * GIB }));

    expect(await saving).toBe(true);
    expect(store.overview()?.gpu_choice).toBe('chosen');
  });

  it('keeps a failed load apart from a failed save, and clears it when trying again works', async () => {
    const loading = store.load();
    backend.expectOne('/api/system/').flush({ error: { code: 'unknown', message: 'Down' } }, { status: 500, statusText: 'Server Error' });
    await loading;

    expect(store.loadError()).not.toBeNull();
    expect(store.error()).toBeNull();
    expect(store.overview()).toBeNull();

    const again = store.load();
    expect(store.loadError()).toBeNull();
    backend.expectOne('/api/system/').flush(overview());
    await again;

    expect(store.overview()?.machine.cpu_count).toBe(16);
  });

  it('reports a refused token without losing what was shown', async () => {
    const loading = store.load();
    backend.expectOne('/api/system/').flush(overview());
    await loading;

    const saving = store.saveHuggingFaceToken('hf_wrong');
    backend
      .expectOne('/api/system/huggingface-token/')
      .flush({ error: { code: 'hf_token_rejected', message: 'No.' } }, { status: 400, statusText: 'Bad Request' });

    expect(await saving).toBe(false);
    expect(store.error()).not.toBeNull();
    expect(store.loadError()).toBeNull();
    expect(store.overview()?.machine.cpu_count).toBe(16);
  });
});
