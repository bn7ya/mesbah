import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Fit, FitSet, Inspection } from '../../data/models.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ModelsStore } from '../../state/models.store';
import { ModelDetailsDialog } from './model-details';

const GIB = 1024 ** 3;

function fit(verdict: Fit['verdict'], required: number, available: number): Fit {
  return { verdict, required_bytes: required * GIB, available_bytes: available * GIB };
}

const WITH_GPU: FitSet = {
  chat: fit('fits', 6, 16),
  chat_full: fit('tight', 16, 16),
  training: fit('too_large', 40, 16),
};

const NO_GPU: FitSet = {
  chat: fit('too_large', 140, 0),
  chat_full: fit('too_large', 280, 0),
  training: fit('cpu_only', 6, 0),
};

function inspection(overrides: Partial<Inspection> = {}): Inspection {
  return {
    repo_id: 'org/model',
    downloads: 10,
    likes: 2,
    pipeline_tag: 'text-generation',
    parameters: 8_000_000_000,
    license: 'apache-2.0',
    gated: false,
    model_type: 'qwen3',
    supports_thinking: true,
    fit: WITH_GPU,
    in_library: null,
    revision: 'abc',
    family: 'dense_decoder',
    architecture: {
      family: 'dense_decoder',
      model_type: 'qwen3',
      layers: 36,
      hidden_size: 4096,
      heads: 32,
      kv_heads: 8,
      vocab_size: 151936,
      context_length: 163840,
      experts: null,
      experts_per_token: null,
      expert_size: null,
    },
    active_parameters: 8_000_000_000,
    has_chat_template: true,
    downloadable: true,
    size_bytes: 16 * GIB,
    disk_free_bytes: 200 * GIB,
    fits_disk: true,
    ...overrides,
  };
}

describe('ModelDetailsDialog', () => {
  const current = signal<Inspection | null>(null);
  const canWrite = signal(true);

  let fixture: ComponentFixture<ModelDetailsDialog>;
  let host: HTMLElement;

  const download = (): HTMLButtonElement => host.querySelector<HTMLButtonElement>('mat-dialog-actions button[matbutton="filled"]')!;
  const plain = (text: string): string => text.replace(/[\u2066-\u2069]/g, '').replace(/\s+/g, ' ').trim();
  const reason = (): string | undefined => {
    const element = host.querySelector('.details__reason');
    return element === null ? undefined : plain(element.textContent);
  };

  async function show(model: Inspection): Promise<void> {
    current.set(model);
    fixture = TestBed.createComponent(ModelDetailsDialog);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  }

  beforeEach(() => {
    localStorage.clear();
    canWrite.set(true);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: MAT_DIALOG_DATA, useValue: { repo: 'org/model' } },
        { provide: MatDialogRef, useValue: { close: vi.fn() } },
        {
          provide: ModelsStore,
          useValue: {
            inspection: current,
            inspecting: signal(false),
            inspectionError: signal<ApiError | null>(null),
            canWrite,
            adding: signal(false),
            inspect: vi.fn(),
            inspectAgain: vi.fn(),
            stopInspecting: vi.fn(),
            add: vi.fn(),
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

  it('lets the download start when the disk has room', async () => {
    await show(inspection());

    expect(download().disabled).toBe(false);
    expect(reason()).toBeUndefined();
  });

  it('turns Download off when the model does not fit on the disk, and gives both sizes', async () => {
    await show(inspection({ fits_disk: false, size_bytes: 42 * GIB, disk_free_bytes: 12 * GIB }));

    expect(download().disabled).toBe(true);
    expect(reason()).toContain("There isn't enough free disk space.");
    expect(reason()).toContain('42 GB');
    expect(reason()).toContain('12 GB');
    expect(download().getAttribute('aria-describedby')).toBe('details-reason');
  });

  it('gives the sizes in Arabic as well', async () => {
    TestBed.inject(LocaleStore).setLocale('ar');
    await show(inspection({ fits_disk: false, size_bytes: 42 * GIB, disk_free_bytes: 12 * GIB }));

    expect(reason()).toContain('لا توجد مساحة كافية على القرص.');
    expect(reason()).toContain('42 GB');
    expect(reason()).toContain('12 GB');
  });

  it('puts the reader being unable to write before the disk', async () => {
    canWrite.set(false);
    await show(inspection({ fits_disk: false }));

    expect(reason()).toBe('Only a trainer or an administrator can download models.');
  });

  it('says a model too large for this machine has no GPU to blame, not a lack of VRAM', async () => {
    await show(inspection({ fit: NO_GPU }));

    const text = plain(host.textContent);
    expect(text).toContain('No GPU found.');
    expect(text).toContain('Too large');
    expect(text).toContain('Needs about 140 GB of memory, more than this machine has');
    expect(text).toContain('CPU only');
    expect(text).toContain('Needs about 6 GB of memory');
    expect(text).not.toContain('of 0 B');
  });

  it('keeps the memory figures against VRAM when a GPU is there', async () => {
    await show(inspection());

    const text = plain(host.textContent);
    expect(text).not.toContain('No GPU found.');
    expect(text).toContain('Needs about 40 GB of 16 GB');
  });

  it('writes the context length as a label before the count', async () => {
    await show(inspection());

    const row = Array.from(host.querySelectorAll('.details__facts dd.details__count'))[0];
    expect(plain(row.textContent)).toBe('token: 163,840');
  });
});
