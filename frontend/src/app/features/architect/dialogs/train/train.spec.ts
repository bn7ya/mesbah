import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import type { DatasetOption, Draft, Source, TrainResult } from '../../data/architect.types';
import { DEFAULT_BLUEPRINT } from '../../data/architect.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ArchitectStore } from '../../state/architect.store';
import { TrainDialog } from './train';

const DRAFT: Draft = {
  id: 'd1',
  name: 'Tiny MoE example',
  notes: '',
  family: 'dense_decoder',
  blueprint: { ...DEFAULT_BLUEPRINT, tokenizer: 'Qwen/Qwen3-0.6B' },
  counts: {
    total: 1,
    active: 1,
    embeddings_share: 0.5,
    parts: { embeddings: 1, attention: 0, feed_forward: 0, router: 0, norms: 0, lm_head: 0 },
  },
  updatedAt: '2026-10-18T10:00:00Z',
  createdBy: 'admin',
};

describe('TrainDialog', () => {
  let fixture: ComponentFixture<TrainDialog>;
  let host: HTMLElement;
  let close: ReturnType<typeof vi.fn>;
  let train: ReturnType<typeof vi.fn<(...args: unknown[]) => Promise<TrainResult>>>;
  const sources = signal<readonly Source[]>([]);
  const datasets = signal<readonly DatasetOption[]>([]);
  const loading = signal(false);
  const loadFailure = signal<ApiError | null>(null);

  const submit = (): HTMLButtonElement => host.querySelector<HTMLButtonElement>('button[type="submit"]')!;
  const option = (list: string, index: number): HTMLElement =>
    host.querySelectorAll<HTMLElement>(`mat-selection-list[name="${list}"] mat-list-option`)[index];

  async function open(): Promise<void> {
    fixture = TestBed.createComponent(TrainDialog);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  }

  async function choose(element: HTMLElement): Promise<void> {
    element.click();
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    close = vi.fn();
    train = vi.fn(() => Promise.resolve<TrainResult>({ started: { project: 'new', run: 'run-1' } }));
    sources.set([
      { id: 'p1', name: 'Support', corrections: 12 },
      { id: 'p2', name: 'Empty', corrections: 0 },
    ]);
    datasets.set([{ id: 'ds1', name: 'org/zen', rows: 1200, hasThinking: true }]);
    loading.set(false);
    loadFailure.set(null);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: MAT_DIALOG_DATA, useValue: { draft: DRAFT } },
        { provide: MatDialogRef, useValue: { close } },
        {
          provide: ArchitectStore,
          useValue: {
            sources,
            datasets,
            sourcesLoading: loading,
            sourcesError: loadFailure,
            training: signal(false),
            loadSources: vi.fn(() => Promise.resolve()),
            train,
          },
        },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('lists the projects and the ready datasets, each with what it holds', async () => {
    await open();

    expect(host.querySelector('input[name="name"]')).toHaveProperty('value', 'Tiny MoE example');
    expect(option('sources', 0).textContent).toContain('Approved replies: 12');
    expect(option('datasets', 0).textContent).toContain('Rows: 1,200');
    expect(option('datasets', 0).textContent).toContain('Includes thinking');
  });

  it('keeps Train disabled, with the reason beside it, until something is chosen', async () => {
    await open();

    expect(submit().disabled).toBe(true);
    expect(host.querySelector('#train-pick')?.textContent.trim()).toBe(en.architect.train.pick);

    await choose(option('datasets', 0));

    expect(submit().disabled).toBe(false);
    expect(host.querySelector('#train-pick')).toBeNull();
  });

  it('does not offer a project that has no approved replies', async () => {
    await open();

    expect(option('sources', 1).getAttribute('aria-disabled')).toBe('true');
    expect(option('sources', 1).textContent).toContain(en.architect.train.none);
  });

  it('asks for an optional row limit per chosen dataset and refuses zero', async () => {
    await open();
    expect(host.querySelector('mat-dialog-content input[type="number"]')).toBeNull();

    await choose(option('datasets', 0));
    const limit = host.querySelector<HTMLInputElement>('mat-dialog-content input[type="number"]')!;
    limit.value = '0';
    limit.dispatchEvent(new Event('input'));
    await fixture.whenStable();

    expect(limit.getAttribute('aria-invalid')).toBe('true');
    expect(host.querySelector('mat-error')?.textContent.trim()).toBe(en.architect.train.limitError);
    expect(submit().disabled).toBe(true);

    limit.value = '';
    limit.dispatchEvent(new Event('input'));
    await fixture.whenStable();

    expect(submit().disabled).toBe(false);
  });

  it('sends the projects and the datasets with their limits, and closes with the run', async () => {
    await open();
    await choose(option('sources', 0));
    await choose(option('datasets', 0));
    const limit = host.querySelector<HTMLInputElement>('mat-dialog-content input[type="number"]')!;
    limit.value = '500';
    limit.dispatchEvent(new Event('input'));
    await fixture.whenStable();

    submit().click();
    await fixture.whenStable();

    expect(train).toHaveBeenCalledWith(DRAFT, 'Tiny MoE example', ['p1'], [{ id: 'ds1', max_rows: 500 }]);
    expect(close).toHaveBeenCalledWith({ project: 'new', run: 'run-1' });
  });

  it('trains on a dataset alone, with no row limit', async () => {
    await open();
    await choose(option('datasets', 0));

    submit().click();
    await fixture.whenStable();

    expect(train).toHaveBeenCalledWith(DRAFT, 'Tiny MoE example', [], [{ id: 'ds1', max_rows: null }]);
  });

  it('shows what the server refused and stays open', async () => {
    train.mockResolvedValue({ error: { code: 'nothing_to_learn', message: en.errors.nothing_to_learn } });
    await open();
    await choose(option('sources', 0));

    submit().click();
    await fixture.whenStable();

    expect(host.querySelector('[role="alert"]')?.textContent).toContain(en.errors.nothing_to_learn);
    expect(close).not.toHaveBeenCalled();
  });

  it('points to the Datasets page when there is nothing to learn from', async () => {
    sources.set([{ id: 'p2', name: 'Empty', corrections: 0 }]);
    datasets.set([]);
    await open();

    const link = host.querySelector<HTMLAnchorElement>('a[href="/datasets"]');
    expect(link?.textContent).toContain(en.architect.train.toDatasets);
    expect(host.querySelector('.train__empty')?.textContent).toContain(en.architect.train.nothing);
    expect(host.querySelector('#train-pick')).toBeNull();
    expect(submit().disabled).toBe(true);
  });
});
