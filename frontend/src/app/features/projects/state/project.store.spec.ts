import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import { errorInterceptor } from '@core/http/error.interceptor';
import { ActiveVersionChanges } from '@shared/version/active-version-changes';
import type { Project } from '../data/projects.types';
import { ProjectStore } from './project.store';

function project(overrides: Partial<Project> = {}): Project {
  return {
    id: 'p1',
    name: 'Support assistant',
    slug: 'support-assistant',
    description: '',
    kind: 'finetune',
    base_model: {
      id: 'm1',
      repo_id: 'org/model',
      family: 'dense_decoder',
      parameters: 2_457_640,
      supports_thinking: false,
      status: 'ready',
    },
    active_version: { id: 'v0', number: 0, name: 'base' },
    system_prompt: '',
    thinking: false,
    generation: { temperature: 0.7, top_p: 0.9, max_tokens: 1024 },
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T10:00:00Z',
    ...overrides,
  };
}

describe('ProjectStore', () => {
  let store: ProjectStore;
  let backend: HttpTestingController;

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function open(overrides: Partial<Project> = {}): Promise<void> {
    store.open('p1');
    await settle();
    backend.expectOne('/api/projects/p1/').flush(project(overrides));
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        ProjectStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { hasAnyGroup: (names: readonly string[]) => names.includes('trainers') } },
      ],
    });
    store = TestBed.inject(ProjectStore);
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

  it('loads the open project with the name of its active version', async () => {
    await open();

    expect(store.project()?.name).toBe('Support assistant');
    expect(store.loading()).toBe(false);
    expect(store.activeVersion()).toEqual({ id: 'v0', number: 0, name: 'base' });
  });

  it('follows the version the versions page makes active', async () => {
    await open();

    TestBed.inject(ActiveVersionChanges).announce({ projectId: 'p1', version: { id: 'v2', number: 2, name: 'Shorter' } });

    expect(store.activeVersion()?.name).toBe('Shorter');
  });

  it('ignores a version made active in another project', async () => {
    await open();

    TestBed.inject(ActiveVersionChanges).announce({ projectId: 'other', version: { id: 'v9', number: 9, name: 'Other' } });

    expect(store.activeVersion()?.name).toBe('base');
  });

  it('sends the change and keeps what the server answers', async () => {
    await open();

    const saving = store.save({ name: 'Orders helper', generation: { temperature: 0.2, top_p: 0.9, max_tokens: 512 } });
    expect(store.saving()).toBe(true);
    const request = backend.expectOne((r) => r.method === 'PATCH');
    expect(request.request.url).toBe('/api/projects/p1/');
    expect(request.request.body).toEqual({
      name: 'Orders helper',
      generation: { temperature: 0.2, top_p: 0.9, max_tokens: 512 },
    });
    request.flush(project({ name: 'Orders helper', generation: { temperature: 0.2, top_p: 0.9, max_tokens: 512 } }));

    expect(await saving).toBeNull();
    await settle();
    expect(store.project()?.name).toBe('Orders helper');
    expect(store.project()?.generation.temperature).toBe(0.2);
    expect(store.saving()).toBe(false);
  });

  it('shows the active version the server reports after the project is changed', async () => {
    await open();

    const saving = store.save({ name: 'Orders helper' });
    backend
      .expectOne((r) => r.method === 'PATCH')
      .flush(project({ name: 'Orders helper', active_version: { id: 'v2', number: 2, name: 'Shorter' } }));
    await saving;

    expect(store.activeVersion()).toEqual({ id: 'v2', number: 2, name: 'Shorter' });
  });

  it('hands a refused change back to the page and keeps the project', async () => {
    await open();

    const saving = store.save({ name: '' });
    backend
      .expectOne((r) => r.method === 'PATCH')
      .flush({ error: { code: 'invalid', message: 'Blank.' } }, { status: 400, statusText: 'Bad Request' });

    expect((await saving)?.code).toBe('invalid');
    expect(store.project()?.name).toBe('Support assistant');
    expect(store.saving()).toBe(false);
  });

  it('removes the project', async () => {
    await open();

    const removing = store.remove();
    const request = backend.expectOne((r) => r.method === 'DELETE');
    expect(request.request.url).toBe('/api/projects/p1/');
    request.flush(null, { status: 204, statusText: 'No Content' });

    expect(await removing).toBeNull();
    expect(store.saving()).toBe(false);
  });

  it('reports a project that does not exist and loads again on request', async () => {
    store.open('p1');
    await settle();
    backend
      .expectOne('/api/projects/p1/')
      .flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });
    await settle();

    expect(store.error()?.code).toBe('not_found');
    expect(store.project()).toBeNull();

    store.reload();
    await settle();
    backend.expectOne('/api/projects/p1/').flush(project());
    await settle();

    expect(store.error()).toBeNull();
    expect(store.project()?.id).toBe('p1');
  });

  it('loads the project again when the same one is opened a second time', async () => {
    await open();

    store.open('p1');
    await settle();
    backend.expectOne('/api/projects/p1/').flush(project({ name: 'Renamed elsewhere' }));
    await settle();

    expect(store.project()?.name).toBe('Renamed elsewhere');
  });

  it('lets trainers and above change a project', () => {
    expect(store.canWrite()).toBe(true);
  });
});
