import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import type { Member } from '../data/members.types';
import { MembersStore } from './members.store';

function member(id: number, overrides: Partial<Member> = {}): Member {
  return {
    id,
    username: `user${id}`,
    first_name: '',
    last_name: '',
    email: '',
    role: 'reviewers',
    owner: false,
    is_active: true,
    is_self: false,
    last_login: null,
    date_joined: '2026-10-18T00:00:00Z',
    ...overrides,
  };
}

function page(rows: Member[]): Page<Member> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

describe('MembersStore', () => {
  let store: MembersStore;
  let backend: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        MembersStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    store = TestBed.inject(MembersStore);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    backend.verify();
    TestBed.resetTestingModule();
  });

  it('asks for the page the paginator shows', async () => {
    const loading = store.load(1, 50);
    const request = backend.expectOne((r) => r.url === '/api/members/');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('50');
    request.flush(page([member(1)]));
    await loading;

    expect(store.pageIndex()).toBe(1);
    expect(store.page().count).toBe(1);
  });

  it('replaces only the changed row', async () => {
    const loading = store.load();
    backend.expectOne((r) => r.url === '/api/members/').flush(page([member(1), member(2)]));
    await loading;

    const changing = store.change(member(2), { role: 'trainers' });
    backend.expectOne('/api/members/2/').flush(member(2, { role: 'trainers' }));

    expect(await changing).toBe(true);
    expect(store.page().results.map((row) => row.role)).toEqual(['reviewers', 'trainers']);
  });

  it('hands a refused addition back to the dialog', async () => {
    const adding = store.add({
      username: 'x',
      password: '1',
      role: 'viewers',
      first_name: '',
      last_name: '',
      email: '',
    });
    backend
      .expectOne('/api/members/')
      .flush({ error: { code: 'weak_password', message: 'Too easy.' } }, { status: 400, statusText: 'Bad Request' });

    expect((await adding)?.code).toBe('weak_password');
  });
});
