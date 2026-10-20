import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { EMPTY_PAGE, type ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ProjectsStore } from '../../state/projects.store';
import { ProjectsPage } from './projects';

describe('ProjectsPage', () => {
  const error = signal<ApiError | null>(null);
  const load = vi.fn(() => Promise.resolve());

  let fixture: ComponentFixture<ProjectsPage>;
  let host: HTMLElement;

  beforeEach(async () => {
    localStorage.clear();
    error.set(null);
    load.mockClear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: ProjectsStore,
          useValue: {
            page: signal(EMPTY_PAGE),
            pageIndex: signal(0),
            pageSize: signal(24),
            loading: signal(false),
            error,
            canWrite: signal(true),
            readyModels: signal([]),
            modelsLoading: signal(false),
            visit: vi.fn(() => Promise.resolve()),
            load,
          },
        },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(ProjectsPage);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('offers no Try again while nothing has failed', () => {
    expect(Array.from(host.querySelectorAll('button')).some((button) => button.textContent.includes('Try again'))).toBe(false);
  });

  it('shows a load failure with a Try again button that loads the list again', async () => {
    error.set({ code: 'unknown', message: 'The server is down.' });
    await fixture.whenStable();

    expect(host.querySelector('[role="alert"]')?.textContent).toContain('The server is down.');
    const retry = Array.from(host.querySelectorAll('button')).find((button) => button.textContent.includes('Try again'));
    retry?.click();

    expect(load).toHaveBeenCalledOnce();
  });
});
