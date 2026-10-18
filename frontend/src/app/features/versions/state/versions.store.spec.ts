import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import { ActiveVersionChanges } from '@shared/version/active-version-changes';
import type { ActiveVersionChange } from '@shared/version/version.types';
import type { Version, VersionChanges, VersionExport } from '../data/versions.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { VersionsStore } from './versions.store';

const LIST = '/api/versions/';

function version(id: string, number: number, parent: string | null, overrides: Partial<Version> = {}): Version {
  return {
    id,
    number,
    name: number === 0 ? 'base' : `Version ${number}`,
    notes: '',
    kind: number === 0 ? 'base' : 'lora',
    parent_id: parent,
    is_active: false,
    children_count: 0,
    size_bytes: number === 0 ? 0 : 84_000_000,
    full_size_bytes: 16_000_000_000,
    lora_rank: number === 0 ? null : 16,
    trains_biases: false,
    delta: null,
    metrics: {},
    created_at: '2026-10-18T10:00:00Z',
    created_by: 'tariq',
    ...overrides,
  };
}

function page(rows: Version[], overrides: Partial<Page<Version>> = {}): Page<Version> {
  return { count: rows.length, next: null, previous: null, results: rows, ...overrides };
}

function exportRow(id: string, status: VersionExport['status'], overrides: Partial<VersionExport> = {}): VersionExport {
  return {
    id,
    version: 'v1',
    format: 'gguf',
    out_type: 'q8_0',
    status,
    error_code: '',
    path: status === 'ready' ? `/data/exports/${id}/model.gguf` : '',
    size_bytes: status === 'ready' ? 14_000_000 : 0,
    downloadable: status === 'ready',
    created_at: '2026-10-18T10:00:00Z',
    finished_at: status === 'ready' ? '2026-10-18T10:01:00Z' : null,
    created_by: 'tariq',
    ...overrides,
  };
}

function exportsPage(rows: VersionExport[]): Page<VersionExport> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

const CHANGES: VersionChanges = {
  version: 'v1',
  modules: ['down_proj', 'k_proj', 'q_proj'],
  layers: [
    { layer: 0, norms: { down_proj: 0.1, k_proj: 0.4, q_proj: 0.8 } },
    { layer: 1, norms: { down_proj: 0.2, k_proj: 0.5, q_proj: 1.0 } },
  ],
  total_norm: 1.4,
  change_from_parent: null,
  parameters: 54_016,
  rank: 16,
};

const TREE: Version[] = [
  version('v0', 0, null, { is_active: true }),
  version('v1', 1, 'v0'),
  version('v2', 2, 'v0'),
  version('v3', 3, 'v1'),
];

describe('VersionsStore', () => {
  let store: VersionsStore;
  let backend: HttpTestingController;
  let asked: (readonly string[])[] = [];

  function list(): TestRequest {
    return backend.expectOne((request) => request.url === LIST && request.method === 'GET');
  }

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function open(rows: Version[] = TREE): Promise<void> {
    store.open('p1');
    await settle();
    list().flush(page(rows));
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    asked = [];
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        VersionsStore,
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
    store = TestBed.inject(VersionsStore);
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

  it('asks for the versions of the open project', async () => {
    store.open('p1');
    await settle();
    const request = list();
    expect(request.request.params.get('project')).toBe('p1');
    expect(request.request.params.get('page_size')).toBe('200');
    expect(store.loading()).toBe(true);
    request.flush(page(TREE));
    await settle();

    expect(store.loading()).toBe(false);
    expect(store.versions()).toHaveLength(4);
  });

  it('follows the pages until every version is here', async () => {
    store.open('p1');
    await settle();
    list().flush(page([TREE[0], TREE[1]], { count: 4, next: 'http://x/?page=2' }));
    await settle();
    const second = list();
    expect(second.request.params.get('page')).toBe('2');
    second.flush(page([TREE[2], TREE[3]], { count: 4 }));
    await settle();

    expect(store.versions().map((row) => row.id)).toEqual(['v0', 'v1', 'v2', 'v3']);
  });

  it('draws each version under the one it was trained from', async () => {
    await open();

    const [root] = store.tree();
    expect(store.tree()).toHaveLength(1);
    expect(root.version.id).toBe('v0');
    expect(root.children.map((node) => node.version.id)).toEqual(['v1', 'v2']);
    expect(root.children[0].children.map((node) => node.version.id)).toEqual(['v3']);
    expect(root.children[1].children).toEqual([]);
  });

  it('shows a lone base as a tree of one', async () => {
    await open([TREE[0]]);

    expect(store.tree()).toHaveLength(1);
    expect(store.tree()[0].children).toEqual([]);
  });

  it('tells the project which version is active once the tree has loaded', async () => {
    const heard: ActiveVersionChange[] = [];
    TestBed.inject(ActiveVersionChanges).changes.subscribe((change) => heard.push(change));

    await open();

    expect(heard).toEqual([{ projectId: 'p1', version: { id: 'v0', number: 0, name: 'base' } }]);
  });

  it('makes one version active, clears the others and tells the project', async () => {
    await open();
    const heard: ActiveVersionChange[] = [];
    TestBed.inject(ActiveVersionChanges).changes.subscribe((change) => heard.push(change));

    const activating = store.activate(TREE[2]);
    expect(store.working()).toEqual(['v2']);
    backend.expectOne('/api/versions/v2/activate/').flush({ ...TREE[2], is_active: true });

    expect(await activating).toBe(true);
    expect(store.versions().filter((row) => row.is_active).map((row) => row.id)).toEqual(['v2']);
    expect(store.working()).toEqual([]);
    expect(heard.map((change) => change.version.id)).toEqual(['v2']);
  });

  it('renames a version and replaces only that row', async () => {
    await open();

    const renaming = store.rename(TREE[1], { name: 'Friendlier' });
    const request = backend.expectOne((r) => r.method === 'PATCH');
    expect(request.request.url).toBe('/api/versions/v1/');
    expect(request.request.body).toEqual({ name: 'Friendlier' });
    request.flush({ ...TREE[1], name: 'Friendlier' });

    expect(await renaming).toBeNull();
    expect(store.versions().map((row) => row.name)).toEqual(['base', 'Friendlier', 'Version 2', 'Version 3']);
  });

  it('hands a refused rename back to the dialog', async () => {
    await open();

    const renaming = store.rename(TREE[1], { name: 'x'.repeat(200) });
    backend
      .expectOne((r) => r.method === 'PATCH')
      .flush({ error: { code: 'invalid', message: 'Too long.' } }, { status: 400, statusText: 'Bad Request' });

    expect((await renaming)?.code).toBe('invalid');
    expect(store.error()).toBeNull();
  });

  it('loads the tree again after a removal, so the children move up', async () => {
    await open();

    const removing = store.remove(TREE[1]);
    backend.expectOne((r) => r.method === 'DELETE').flush(null, { status: 204, statusText: 'No Content' });
    await vi.advanceTimersByTimeAsync(0);
    list().flush(page([TREE[0], version('v2', 2, 'v0'), version('v3', 3, 'v0')]));

    expect(await removing).toBe(true);
    expect(store.tree()[0].children.map((node) => node.version.id)).toEqual(['v2', 'v3']);
  });

  it('keeps the base and says why in the reader\'s language', async () => {
    await open();
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');

    const removing = store.remove(TREE[0]);
    backend
      .expectOne((r) => r.method === 'DELETE')
      .flush({ error: { code: 'root_version_kept', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

    expect(await removing).toBe(false);
    expect(store.error()?.code).toBe('root_version_kept');
    expect(store.error()?.message).toBe(en.errors.root_version_kept);
    expect(store.versions()).toHaveLength(4);
    expect(store.working()).toEqual([]);
  });

  it('keeps the active version and says why in the reader\'s language', async () => {
    await open();
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('ar');

    const removing = store.remove(TREE[0]);
    backend
      .expectOne((r) => r.method === 'DELETE')
      .flush({ error: { code: 'active_version_kept', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

    expect(await removing).toBe(false);
    expect(store.error()?.message).toBe(ar.errors.active_version_kept);
  });

  it('reports a tree that could not load and loads again on request', async () => {
    store.open('p1');
    await settle();
    list().flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });
    await settle();

    expect(store.loadError()?.code).toBe('not_found');
    expect(store.versions()).toEqual([]);

    store.reload();
    await settle();
    list().flush(page(TREE));
    await settle();

    expect(store.loadError()).toBeNull();
    expect(store.versions()).toHaveLength(4);
  });

  it('lets trainers and above change the tree, and no one below', () => {
    expect(store.canWrite()).toBe(true);
    expect(asked).toEqual([['trainers', 'admins']]);
  });
  describe('what changed', () => {
    it('loads the change of the version being looked at and draws it as a map', async () => {
      store.showChanges('v1');
      await settle();
      expect(store.changesLoading()).toBe(true);
      backend.expectOne('/api/versions/v1/changes/').flush(CHANGES);
      await settle();

      expect(store.changesLoading()).toBe(false);
      expect(store.versionChanges()?.rank).toBe(16);
      expect(store.changeMap()?.modules).toEqual(['q_proj', 'k_proj', 'down_proj']);
      expect(store.changeMap()?.rows).toHaveLength(2);
    });

    it('forgets the change when the dialog closes', async () => {
      store.showChanges('v1');
      await settle();
      backend.expectOne('/api/versions/v1/changes/').flush(CHANGES);
      await settle();

      store.forgetChanges();
      await settle();

      expect(store.versionChanges()).toBeNull();
      expect(store.changeMap()).toBeNull();
    });

    it('reports a change that could not load and loads again on request', async () => {
      store.showChanges('v1');
      await settle();
      backend
        .expectOne('/api/versions/v1/changes/')
        .flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });
      await settle();

      expect(store.changesLoadError()?.code).toBe('not_found');

      store.reloadChanges();
      await settle();
      backend.expectOne('/api/versions/v1/changes/').flush(CHANGES);
      await settle();

      expect(store.changesLoadError()).toBeNull();
      expect(store.changeMap()?.rows).toHaveLength(2);
    });
  });

  describe('exports', () => {
    const EXPORTS = '/api/versions/v1/exports/';

    function exportsList(): TestRequest {
      return backend.expectOne((request) => request.url === EXPORTS && request.method === 'GET');
    }

    async function showExports(rows: VersionExport[]): Promise<void> {
      store.showExports('v1');
      await settle();
      exportsList().flush(exportsPage(rows));
      await settle();
    }

    it('lists the exports of the version being looked at', async () => {
      store.showExports('v1');
      await settle();
      const request = exportsList();
      expect(request.request.params.get('page_size')).toBe('200');
      expect(store.exportsLoading()).toBe(true);
      request.flush(exportsPage([exportRow('e1', 'ready'), exportRow('e2', 'queued')]));
      await settle();

      expect(store.exportsLoading()).toBe(false);
      expect(store.exportsLoaded()).toBe(true);
      expect(store.exports().map((row) => row.id)).toEqual(['e1', 'e2']);
      expect(store.unfinishedExports()).toBe(true);
    });

    it('starts an export and puts it at the top of the open list', async () => {
      await showExports([exportRow('e1', 'ready')]);

      const creating = store.createExport(TREE[1], { format: 'gguf', out_type: 'q8_0' });
      const request = backend.expectOne((r) => r.method === 'POST');
      expect(request.request.url).toBe(EXPORTS);
      expect(request.request.body).toEqual({ format: 'gguf', out_type: 'q8_0' });
      request.flush(exportRow('e2', 'queued'), { status: 202, statusText: 'Accepted' });

      expect(await creating).toBeNull();
      expect(store.exports().map((row) => row.id)).toEqual(['e2', 'e1']);
      expect(store.unfinishedExports()).toBe(true);
    });

    it('sends only the format for a LoRA export', async () => {
      const creating = store.createExport(TREE[1], { format: 'lora' });
      const request = backend.expectOne((r) => r.method === 'POST');
      expect(request.request.body).toEqual({ format: 'lora' });
      request.flush(exportRow('e3', 'queued', { format: 'lora', out_type: '' }), { status: 202, statusText: 'Accepted' });

      expect(await creating).toBeNull();
    });

    it('hands a refused export back to the dialog in the reader\'s language', async () => {
      const locale = TestBed.inject(LocaleStore);
      locale.register({ en, ar });
      locale.setLocale('en');

      const creating = store.createExport(TREE[0], { format: 'lora' });
      backend
        .expectOne((r) => r.method === 'POST')
        .flush({ error: { code: 'not_exportable', message: 'raw' } }, { status: 409, statusText: 'Conflict' });

      const failure = await creating;
      expect(failure?.code).toBe('not_exportable');
      expect(failure?.message).toBe(en.errors.not_exportable);
    });

    it('polls every three seconds while an export is unfinished, and stops when it is done', async () => {
      await showExports([exportRow('e1', 'running')]);
      const watching = store.watchExports().subscribe();
      await settle();

      await vi.advanceTimersByTimeAsync(2999);
      backend.expectNone(EXPORTS);

      await vi.advanceTimersByTimeAsync(1);
      exportsList().flush(exportsPage([exportRow('e1', 'running')]));
      await settle();
      expect(store.exports()[0].status).toBe('running');

      await vi.advanceTimersByTimeAsync(3000);
      exportsList().flush(exportsPage([exportRow('e1', 'ready')]));
      await settle();
      expect(store.exports()[0].status).toBe('ready');
      expect(store.unfinishedExports()).toBe(false);

      await vi.advanceTimersByTimeAsync(9000);
      backend.expectNone(EXPORTS);
      watching.unsubscribe();
    });

    it('does not poll when everything is finished', async () => {
      await showExports([exportRow('e1', 'ready'), exportRow('e2', 'failed', { error_code: 'out_of_memory' })]);
      const watching = store.watchExports().subscribe();
      await settle();

      await vi.advanceTimersByTimeAsync(9000);

      backend.expectNone(EXPORTS);
      watching.unsubscribe();
    });

    it('stops polling when the page leaves', async () => {
      await showExports([exportRow('e1', 'queued')]);
      const watching = store.watchExports().subscribe();
      await settle();

      watching.unsubscribe();
      await vi.advanceTimersByTimeAsync(9000);

      backend.expectNone(EXPORTS);
    });

    it('keeps the list when a poll fails and tries again at the next tick', async () => {
      await showExports([exportRow('e1', 'running')]);
      const watching = store.watchExports().subscribe();
      await settle();

      await vi.advanceTimersByTimeAsync(3000);
      exportsList().flush({ error: { code: 'unknown', message: 'x' } }, { status: 500, statusText: 'Server Error' });
      await settle();
      expect(store.exports()).toHaveLength(1);
      expect(store.exportsLoadError()).toBeNull();

      await vi.advanceTimersByTimeAsync(3000);
      exportsList().flush(exportsPage([exportRow('e1', 'ready')]));
      await settle();
      expect(store.exports()[0].status).toBe('ready');
      watching.unsubscribe();
    });

    it('removes an export from the list and calls the server', async () => {
      await showExports([exportRow('e1', 'ready'), exportRow('e2', 'ready')]);

      const removing = store.removeExport(store.exports()[0]);
      expect(store.exportsWorking()).toEqual(['e1']);
      const request = backend.expectOne((r) => r.method === 'DELETE');
      expect(request.request.url).toBe('/api/versions/exports/e1/');
      request.flush(null, { status: 204, statusText: 'No Content' });

      expect(await removing).toBe(true);
      expect(store.exports().map((row) => row.id)).toEqual(['e2']);
      expect(store.exportsWorking()).toEqual([]);
    });

    it('keeps the export and the reason when a removal is refused', async () => {
      await showExports([exportRow('e1', 'ready')]);

      const removing = store.removeExport(store.exports()[0]);
      backend
        .expectOne((r) => r.method === 'DELETE')
        .flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });

      expect(await removing).toBe(false);
      expect(store.exportsError()?.code).toBe('not_found');
      expect(store.exports()).toHaveLength(1);
      expect(store.exportsWorking()).toEqual([]);
    });

    it('ignores a poll that began before a removal', async () => {
      await showExports([exportRow('e1', 'running'), exportRow('e2', 'ready')]);
      const watching = store.watchExports().subscribe();
      await settle();

      await vi.advanceTimersByTimeAsync(3000);
      const stale = exportsList();
      const removing = store.removeExport(store.exports()[1]);
      backend.expectOne((r) => r.method === 'DELETE').flush(null, { status: 204, statusText: 'No Content' });
      expect(await removing).toBe(true);
      stale.flush(exportsPage([exportRow('e1', 'running'), exportRow('e2', 'ready')]));
      await settle();

      expect(store.exports().map((row) => row.id)).toEqual(['e1']);
      watching.unsubscribe();
    });

    it('points a download at the file endpoint', () => {
      expect(store.downloadUrl(exportRow('e1', 'ready'))).toBe('/api/versions/exports/e1/download/');
    });

    it('reports exports that could not load', async () => {
      store.showExports('v1');
      await settle();
      exportsList().flush({ error: { code: 'not_found', message: 'Not found.' } }, { status: 404, statusText: 'Not Found' });
      await settle();

      expect(store.exportsLoadError()?.code).toBe('not_found');
      expect(store.exports()).toEqual([]);
    });
  });
});
