import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { EMPTY } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError, Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import type { HubQuery, HubResult, LibraryModel } from '../../data/models.types';
import { POPULAR } from '../../data/models.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ModelsStore } from '../../state/models.store';
import { ModelsPage } from './models';

const GIB = 1024 ** 3;

function model(id: string, overrides: Partial<LibraryModel>): LibraryModel {
  return {
    id,
    repo_id: `org/${id}`,
    origin: 'hub',
    revision: 'abc',
    family: 'dense_decoder',
    model_type: 'qwen3',
    architecture: {
      family: 'dense_decoder',
      model_type: 'qwen3',
      layers: 12,
      hidden_size: 512,
      heads: 8,
      kv_heads: 8,
      vocab_size: 32000,
      context_length: 2048,
      experts: null,
      experts_per_token: null,
      expert_size: null,
    },
    parameters: 1_000_000_000,
    active_parameters: 1_000_000_000,
    license: '',
    gated: false,
    supports_thinking: false,
    has_chat_template: true,
    size_bytes: GIB,
    downloaded_bytes: GIB,
    status: 'ready',
    error_code: '',
    downloaded_at: null,
    created_at: '2026-10-18T10:00:00Z',
    fit: {
      chat: { verdict: 'fits', required_bytes: GIB, available_bytes: 16 * GIB },
      chat_full: { verdict: 'fits', required_bytes: GIB, available_bytes: 16 * GIB },
      training: { verdict: 'fits', required_bytes: GIB, available_bytes: 16 * GIB },
    },
    ...overrides,
  };
}

const LIBRARY: Page<LibraryModel> = {
  count: 2,
  next: null,
  previous: null,
  results: [model('downloaded', {}), model('trained', { repo_id: 'local/my-model', origin: 'trained' })],
};

describe('ModelsPage', () => {
  const remove = vi.fn<(target: LibraryModel) => Promise<boolean>>();

  let fixture: ComponentFixture<ModelsPage>;
  let host: HTMLElement;

  async function ask(repo: string): Promise<string> {
    const card = Array.from(host.querySelectorAll<HTMLElement>('.models__row')).find((row) => row.textContent.includes(repo))!;
    card.querySelector<HTMLButtonElement>('.models__actions button:last-child')!.click();
    await fixture.whenStable();
    const dialog = document.querySelector('mat-dialog-container');
    if (dialog === null) {
      throw new Error('no confirmation');
    }
    return dialog.textContent.replace(/\s+/g, ' ').trim();
  }

  beforeEach(async () => {
    localStorage.clear();
    remove.mockReset().mockResolvedValue(true);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: ModelsStore,
          useValue: {
            page: signal(LIBRARY),
            pageIndex: signal(0),
            pageSize: signal(25),
            loading: signal(false),
            error: signal<ApiError | null>(null),
            canWrite: signal(true),
            hubQuery: signal<HubQuery>(POPULAR),
            hubResults: signal<readonly HubResult[]>([]),
            hubLoading: signal(false),
            hubError: signal<ApiError | null>(null),
            working: signal<readonly string[]>([]),
            load: vi.fn(() => Promise.resolve()),
            watchDownloads: () => EMPTY,
            search: vi.fn(),
            searchAgain: vi.fn(),
            remove,
          },
        },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(ModelsPage);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  afterEach(() => {
    document.body.querySelectorAll('.cdk-overlay-container').forEach((container) => (container.innerHTML = ''));
    TestBed.resetTestingModule();
  });

  it('says a downloaded model stays on HuggingFace and can be downloaded again', async () => {
    const text = await ask('org/downloaded');

    expect(text).toContain('The model stays on HuggingFace and can be downloaded again.');
  });

  it('says a model trained here is removed for good, with nothing to download again', async () => {
    const text = await ask('local/my-model');

    expect(text).toContain("The model's files are deleted from this machine for good.");
    expect(text).not.toContain('HuggingFace and can be downloaded again');
  });

  it('says it in Arabic too', async () => {
    TestBed.inject(LocaleStore).setLocale('ar');
    await fixture.whenStable();

    const text = await ask('local/my-model');

    expect(text).toContain('تحذف ملفات النموذج من هذا الجهاز نهائيا.');
  });
});
