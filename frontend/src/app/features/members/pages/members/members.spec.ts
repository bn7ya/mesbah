import { BreakpointObserver } from '@angular/cdk/layout';
import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError, Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Member } from '../../data/members.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { MembersStore } from '../../state/members.store';
import { MembersPage } from './members';

function member(overrides: Partial<Member>): Member {
  return {
    id: 1,
    username: 'noor',
    first_name: 'Noor',
    last_name: '',
    email: '',
    role: 'reviewers',
    owner: false,
    is_active: true,
    is_self: false,
    last_login: null,
    date_joined: '2026-10-01T10:00:00Z',
    ...overrides,
  };
}

const MEMBERS: Page<Member> = {
  count: 4,
  next: null,
  previous: null,
  results: [
    member({ id: 1, username: 'admin', first_name: '', role: 'admins', owner: true, is_self: true }),
    member({ id: 2, username: 'noor' }),
    member({ id: 3, username: 'rana', first_name: 'Rana', is_active: false }),
    member({ id: 4, username: 'tariq', first_name: 'Tariq', role: 'trainers' }),
  ],
};

describe('MembersPage', () => {
  let fixture: ComponentFixture<MembersPage>;
  let host: HTMLElement;

  const headers = (): string[] =>
    Array.from(host.querySelectorAll('th')).map((cell) => cell.textContent.trim());
  const buttonNames = (): string[] =>
    Array.from(host.querySelectorAll('td button[aria-label]'))
      .map((button) => button.getAttribute('aria-label') ?? '')
      .filter((name) => /^(Deactivate|Reactivate) /.test(name));

  async function show(wide: boolean): Promise<void> {
    TestBed.configureTestingModule({
      providers: [
        { provide: BreakpointObserver, useValue: { observe: () => of({ matches: wide, breakpoints: {} }) } },
        {
          provide: MembersStore,
          useValue: {
            page: signal(MEMBERS),
            pageIndex: signal(0),
            pageSize: signal(25),
            loading: signal(false),
            busy: signal(false),
            error: signal<ApiError | null>(null),
            load: vi.fn(() => Promise.resolve()),
            change: vi.fn(() => Promise.resolve(true)),
          },
        },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(MembersPage);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('names every Deactivate and Reactivate button after the member it acts on', async () => {
    await show(true);

    expect(buttonNames()).toEqual(['Deactivate noor', 'Reactivate rana', 'Deactivate tariq']);
  });

  it('keeps the visible words of those buttons inside their names', async () => {
    await show(true);

    const visible = Array.from(host.querySelectorAll('td button[aria-label]'))
      .filter((button) => /^(Deactivate|Reactivate) /.test(button.getAttribute('aria-label') ?? ''))
      .map((button) => button.textContent.trim());

    expect(visible).toEqual(['Deactivate', 'Reactivate', 'Deactivate']);
  });

  it('shows the status as a column of its own on a wide screen', async () => {
    await show(true);

    expect(headers()).toEqual(['Person', 'Role', 'Status', 'Actions']);
  });

  it('folds the status and the action under the person on a narrow screen', async () => {
    await show(false);

    expect(headers()).toEqual(['Person', 'Role']);
    const person = host.querySelectorAll<HTMLElement>('tr.mat-mdc-row')[2].querySelector('td')!;
    expect(person.textContent).toContain('Rana');
    expect(person.textContent).toContain('Deactivated');
    expect(person.querySelector('button')?.getAttribute('aria-label')).toBe('Reactivate rana');
    expect(buttonNames()).toEqual(['Deactivate noor', 'Reactivate rana', 'Deactivate tariq']);
  });

  it('offers no action on the owner or on the signed-in account', async () => {
    await show(false);

    const owner = host.querySelectorAll<HTMLElement>('tr.mat-mdc-row')[0].querySelector('td')!;
    expect(owner.querySelector('button')).toBeNull();
  });
});
