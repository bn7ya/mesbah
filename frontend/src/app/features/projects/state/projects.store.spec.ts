import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Project } from '../data/projects.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { ProjectsStore } from './projects.store';

const LIST = '/api/projects/';
const MODELS = '/api/models/';

function project(id: string, overrides: Partial<Project> = {}): Project {
  return {
    id,
    name: `Project ${id}`,
    slug: `project-${id}`,
    description: '',
    kind: 'finetune',
    base_model: {
      id: 'm1',
      repo_id: 'org/model',
      family: 'dense_decoder',
      parameters: 2_457_640,
      supports_thinking: true,
      status: 'ready',
    },
    active_version: { id: `v-${id}`, number: 0, name: 'base' },
    system_prompt: '',
    thinking: true,
    generation: { temperature: 0.7, top_p: 0.9, max_tokens: 1024 },
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T10:00:00Z',
    ...overrides,
  };
}

function page<T>(rows: T[], count = rows.length): Page<T> {
  return { count, next: null, previous: null, results: rows };
}

function model(id: string, status: string): Record<string, unknown> {
  return { id, repo_id: `org/${id}`, parameters: 8_190_735_360, supports_thinking: id === 'think', status, size_bytes: 1 };
}

describe('ProjectsStore', () => {
  let store: ProjectsStore;
  let backend: HttpTestingController;

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  function modelsRequest(rows: Record<string, unknown>[]): void {
    const request = backend.expectOne((r) => r.url === MODELS);
    expect(request.request.params.get('page_size')).toBe('200');
    request.flush(page(rows));
  }

  async function loadProjects(rows: Project[], count = rows.length): Promise<void> {
    const loading = store.load();
    backend.expectOne((r) => r.url === LIST && r.method === 'GET').flush(page(rows, count));
    await loading;
    await vi.advanceTimersByTimeAsync(0);
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        ProjectsStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: (names: readonly string[]) => names.includes('trainers') } },
      ],
    });
    store = TestBed.inject(ProjectsStore);
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
    await settle();
    modelsRequest([]);
    const loading = store.load(1, 48);
    const request = backend.expectOne((r) => r.url === LIST && r.method === 'GET');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('48');
    request.flush(page([], 60));
    await loading;

    expect(store.pageIndex()).toBe(1);
    expect(store.page().count).toBe(60);
    expect(store.loading()).toBe(false);
  });

  it('starts each visit from the first page with no card left over from the last one', async () => {
    await settle();
    modelsRequest([]);
    await loadProjects([project('a')], 60);
    const turning = store.load(2, 24);
    backend.expectOne((r) => r.url === LIST && r.method === 'GET').flush(page([project('c')], 60));
    await turning;

    const visiting = store.visit();
    expect(store.page().results).toEqual([]);
    const request = backend.expectOne((r) => r.url === LIST && r.method === 'GET');
    expect(request.request.params.get('page')).toBe('1');
    request.flush(page([]));
    await visiting;
    await settle();
    modelsRequest([]);
    expect(store.pageIndex()).toBe(0);
  });

  it('reports a list that failed to load', async () => {
    await settle();
    modelsRequest([]);
    const loading = store.load();
    backend
      .expectOne((r) => r.url === LIST && r.method === 'GET')
      .flush({ error: { code: 'server', message: 'Down.' } }, { status: 500, statusText: 'Server Error' });
    await loading;

    expect(store.error()?.code).toBe('server');
    expect(store.loading()).toBe(false);
  });

  it('offers only the models that finished downloading', async () => {
    await settle();
    modelsRequest([model('ready', 'ready'), model('busy', 'downloading'), model('failed', 'failed'), model('think', 'ready')]);
    await settle();

    expect(store.readyModels().map((row) => row.id)).toEqual(['ready', 'think']);
    expect(store.readyModels()[1]).toEqual({ id: 'think', repo_id: 'org/think', parameters: 8_190_735_360, supports_thinking: true });
    expect(store.modelsLoading()).toBe(false);
  });

  it('reads the library again each time the page loads', async () => {
    await settle();
    modelsRequest([]);
    await settle();

    const loading = store.load();
    backend.expectOne((r) => r.url === LIST && r.method === 'GET').flush(page([]));
    await loading;
    await settle();
    modelsRequest([model('ready', 'ready')]);
    await settle();

    expect(store.readyModels()).toHaveLength(1);
  });

  it('creates a project and returns it', async () => {
    await settle();
    modelsRequest([model('ready', 'ready')]);

    const creating = store.create({ name: 'Orders helper', base_model: 'ready', thinking: false });
    expect(store.creating()).toBe(true);
    const request = backend.expectOne((r) => r.url === LIST && r.method === 'POST');
    expect(request.request.body).toEqual({ name: 'Orders helper', base_model: 'ready', thinking: false });
    request.flush(project('new', { name: 'Orders helper' }), { status: 201, statusText: 'Created' });

    const result = await creating;
    expect('project' in result && result.project.name).toBe('Orders helper');
    expect(store.creating()).toBe(false);
  });

  it('hands the refusal back in the reader\'s language', async () => {
    await settle();
    modelsRequest([]);
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');

    const creating = store.create({ name: 'Orders helper', base_model: 'busy' });
    backend
      .expectOne((r) => r.url === LIST && r.method === 'POST')
      .flush({ error: { code: 'base_model_not_ready', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

    const result = await creating;
    expect('error' in result && result.error.code).toBe('base_model_not_ready');
    expect('error' in result && result.error.message).toBe(en.errors.base_model_not_ready);
    expect(store.creating()).toBe(false);
  });

  it('lets trainers and above start projects', async () => {
    expect(store.canWrite()).toBe(true);
    await settle();
    modelsRequest([]);
  });
});
