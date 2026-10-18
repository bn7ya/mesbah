import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthStore } from '@core/auth/state/auth.store';
import type { Page } from '@core/http/api.types';
import { errorInterceptor } from '@core/http/error.interceptor';
import { LocaleStore } from '@core/i18n/locale.store';
import type { Counts, Design, DraftWire, Estimate, Fit, PresetWire } from '../data/architect.types';
import ar from '../i18n/ar.json';
import en from '../i18n/en.json';
import { ArchitectStore } from './architect.store';

const PRESETS = '/api/architect/presets/';
const ESTIMATE = '/api/architect/estimate/';
const DRAFTS = '/api/architect/drafts/';
const PROJECTS = '/api/projects/';
const PLAN = '/api/training/plan/';
const DATASETS = '/api/datasets/';
const GIB = 1024 ** 3;

const MOE_DESIGN: Design = {
  family: 'moe_decoder',
  layers: 16,
  hidden_size: 1024,
  heads: 16,
  kv_heads: 4,
  intermediate_size: 2304,
  vocab_size: 32000,
  context_length: 4096,
  experts: 8,
  experts_per_token: 2,
  encoder_layers: 0,
  decoder_layers: 0,
  tie_embeddings: true,
};

const DENSE_DESIGN: Design = {
  ...MOE_DESIGN,
  family: 'dense_decoder',
  experts: 0,
  experts_per_token: 0,
};

const COUNTS: Counts = {
  total: 980_847_616,
  active: 301_370_368,
  embeddings_share: 0.033,
  parts: {
    embeddings: 32_768_000,
    attention: 41_943_040,
    feed_forward: 905_969_664,
    router: 131_072,
    norms: 35_840,
    lm_head: 0,
  },
};

function fit(verdict: Fit['verdict'] = 'fits'): Fit {
  return { verdict, required_bytes: 6 * GIB, available_bytes: 16 * GIB };
}

function estimate(design: Design = DENSE_DESIGN, tokenizerVocabulary: number | null = null): Estimate {
  return {
    design,
    counts: COUNTS,
    memory: {
      precision: 'bf16_mixed',
      weights_bytes: 2 * GIB,
      adamw_bytes: 8 * GIB,
      adamw_8bit_bytes: 5 * GIB,
      activation_bytes: GIB,
      training_bytes: 10 * GIB,
      training_8bit_bytes: 7 * GIB,
      fit: fit(),
      fit_8bit: fit(),
    },
    note: null,
    tokenizer_vocabulary: tokenizerVocabulary,
  };
}

function draftWire(id: string, overrides: Partial<DraftWire> = {}): DraftWire {
  return {
    ...estimate(),
    id,
    name: `Design ${id}`,
    notes: '',
    tokenizer: 'trl-internal-testing/tiny-Qwen3ForCausalLM',
    seq_len: 512,
    batch: 4,
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T11:00:00Z',
    created_by: 'admin',
    ...overrides,
  };
}

function preset(name: string, design: Design): PresetWire {
  return { name, design, counts: COUNTS };
}

function page<T>(rows: T[], count = rows.length): Page<T> {
  return { count, next: null, previous: null, results: rows };
}

describe('ArchitectStore', () => {
  let store: ArchitectStore;
  let backend: HttpTestingController;
  let locale: LocaleStore;
  let groups: readonly string[] = ['trainers'];

  async function settle(): Promise<void> {
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
  }

  async function pause(): Promise<void> {
    await vi.advanceTimersByTimeAsync(400);
  }

  function estimateRequest(): TestRequest {
    return backend.expectOne((request) => request.url === ESTIMATE && request.method === 'POST');
  }

  async function startUp(role: readonly string[] = ['trainers']): Promise<void> {
    groups = role;
    store = TestBed.inject(ArchitectStore);
    await settle();
    backend.expectOne(PRESETS).flush({ presets: [preset('dense_100m', DENSE_DESIGN), preset('moe_1b', MOE_DESIGN)] });
    await pause();
    estimateRequest().flush(estimate());
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        ArchitectStore,
        provideRouter([]),
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        {
          provide: AuthStore,
          useValue: { hasAnyGroup: (names: readonly string[]) => groups.some((group) => names.includes(group)) },
        },
      ],
    });
    backend = TestBed.inject(HttpTestingController);
    locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
  });

  afterEach(() => {
    try {
      backend.verify();
    } finally {
      TestBed.resetTestingModule();
      vi.useRealTimers();
    }
  });

  describe('starting points', () => {
    it('loads the ready-made designs as editable blueprints', async () => {
      await startUp();

      expect(store.presets().map((item) => item.name)).toEqual(['dense_100m', 'moe_1b']);
      const moe = store.presets()[1];
      expect(moe.family).toBe('moe_decoder');
      expect(moe.blueprint.experts).toBe(8);
      expect(moe.blueprint.encoder_layers).toBe(6);
    });

    it('keeps the tokenizer and the sizing when a design is chosen', async () => {
      await startUp();
      store.setTokenizer('Qwen/Qwen3-0.6B');
      store.setNumber('seq_len', 256);

      store.usePreset(store.presets()[1]);

      expect(store.blueprint().family).toBe('moe_decoder');
      expect(store.blueprint().tokenizer).toBe('Qwen/Qwen3-0.6B');
      expect(store.blueprint().seq_len).toBe(256);
      expect(store.startedFrom()).toBe('moe_1b');
      expect(store.draft()).toBeNull();
      await settle();
      await pause();
      estimateRequest().flush(estimate(MOE_DESIGN));
    });

    it('labels a ready-made design in words and falls back to its name', async () => {
      await startUp();

      expect(store.presetLabel('moe_1b')).toBe(en.architect.preset.moe_1b);
      expect(store.presetLabel('something_new')).toBe('something_new');
    });
  });

  describe('estimating', () => {
    it('asks once, after the reader stops typing', async () => {
      await startUp();

      store.setNumber('layers', 13);
      await settle();
      await vi.advanceTimersByTimeAsync(200);
      store.setNumber('layers', 14);
      await settle();
      expect(store.estimating()).toBe(true);

      await vi.advanceTimersByTimeAsync(399);
      backend.expectNone(ESTIMATE);
      await vi.advanceTimersByTimeAsync(1);
      const request = estimateRequest();
      expect(request.request.body).toMatchObject({ seq_len: 1024, batch: 8, design: { layers: 14 } });
      request.flush(estimate());
      await settle();

      expect(store.estimating()).toBe(false);
      expect(store.estimate()?.counts.total).toBe(COUNTS.total);
    });

    it('sends only the fields the family uses', async () => {
      await startUp();

      store.setFamily('encoder_decoder');
      await settle();
      await pause();
      const request = estimateRequest();
      expect(request.request.body).toEqual({
        design: {
          family: 'encoder_decoder',
          hidden_size: 768,
          heads: 12,
          intermediate_size: 2048,
          vocab_size: 32000,
          context_length: 2048,
          tie_embeddings: true,
          encoder_layers: 6,
          decoder_layers: 6,
        },
        seq_len: 1024,
        batch: 8,
        tokenizer: '',
      });
      request.flush(estimate());
    });

    it('sends the tokenizer with the rest, after the reader stops typing', async () => {
      await startUp();

      store.setTokenizer(' Qwen/Qwen3-0.6B ');
      await settle();
      await vi.advanceTimersByTimeAsync(399);
      backend.expectNone(ESTIMATE);
      await vi.advanceTimersByTimeAsync(1);
      const request = estimateRequest();
      expect(request.request.body).toMatchObject({ tokenizer: 'Qwen/Qwen3-0.6B', seq_len: 1024, batch: 8 });
      request.flush(estimate());
    });

    it('asks again when only the tokenizer changes', async () => {
      await startUp();

      store.setTokenizer('Qwen/Qwen3-0.6B');
      await settle();
      await pause();
      estimateRequest().flush(estimate());
      await settle();
      store.setTokenizer('Qwen/Qwen3-1.7B');
      await settle();
      await pause();

      const request = estimateRequest();
      expect(request.request.body).toMatchObject({ tokenizer: 'Qwen/Qwen3-1.7B' });
      request.flush(estimate());
    });

    it('names the field a refused design is about, in the reader language', async () => {
      await startUp();

      store.setNumber('heads', 5);
      await settle();
      await pause();
      estimateRequest().flush(
        {
          error: {
            code: 'design_not_divisible',
            message: 'The hidden size must divide evenly between the heads.',
            fields: { heads: ['The hidden size must divide evenly between the heads.'] },
          },
        },
        { status: 400, statusText: 'Bad Request' },
      );
      await settle();

      expect(store.estimate()).toBeNull();
      expect(store.fieldErrors().heads).toBe(en.errors.design_not_divisible);
      expect(store.hasFieldErrors()).toBe(true);
      expect(store.refusalSummary()).toBeNull();
      expect(store.canSave()).toBe(false);
      expect(store.estimating()).toBe(false);
    });

    it('says what the key-value heads must divide into', async () => {
      await startUp();

      store.setNumber('kv_heads', 3);
      await settle();
      await pause();
      estimateRequest().flush(
        {
          error: {
            code: 'design_not_divisible',
            message: 'The hidden size must divide evenly between the heads.',
            fields: { kv_heads: ['The hidden size must divide evenly between the heads.'] },
          },
        },
        { status: 400, statusText: 'Bad Request' },
      );
      await settle();

      expect(store.fieldErrors().kv_heads).toBe(en.architect.error.kvNotDivisible);
    });

    it('shows the allowed range for a number outside it', async () => {
      await startUp();

      store.setNumber('hidden_size', 8);
      await settle();
      await pause();
      estimateRequest().flush(
        {
          error: {
            code: 'design_out_of_range',
            message: 'This is outside what Mesbah can build.',
            fields: { hidden_size: ['This is outside what Mesbah can build.'] },
          },
        },
        { status: 400, statusText: 'Bad Request' },
      );
      await settle();

      expect(store.fieldErrors().hidden_size).toBe('Use a whole number from 16 to 65,536.');
    });

    it('reports a refusal that names no field in the page', async () => {
      await startUp();

      store.estimateAgain();
      await settle();
      await pause();
      estimateRequest().flush(
        { error: { code: 'design_tied_only', message: 'raw', fields: { tie_embeddings: ['raw'] } } },
        { status: 400, statusText: 'Bad Request' },
      );
      await settle();

      expect(store.hasFieldErrors()).toBe(false);
      expect(store.refusalSummary()?.message).toBe(en.errors.design_tied_only);
    });

    it('does not ask while the sequence length or batch is outside its range', async () => {
      await startUp();

      store.setNumber('seq_len', 10);
      store.setNumber('batch', null);
      await settle();
      await pause();
      backend.expectNone(ESTIMATE);

      expect(store.estimate()).toBeNull();
      expect(store.estimating()).toBe(false);
      expect(store.fieldErrors().seq_len).toBe('Use a whole number from 64 to 131,072.');
      expect(store.fieldErrors().batch).toBe(en.errors.design_missing);

      store.setNumber('seq_len', 512);
      store.setNumber('batch', 4);
      await settle();
      await pause();
      estimateRequest().flush(estimate());
      await settle();

      expect(store.hasFieldErrors()).toBe(false);
      expect(store.estimate()).not.toBeNull();
    });
  });

  describe('the tokenizer vocabulary', () => {
    const NAME = 'Qwen/Qwen3-0.6B';
    const SIZE = 151_936;
    const RAISED: Design = { ...DENSE_DESIGN, vocab_size: SIZE };

    async function typeIn(vocabulary: number, answer: Estimate): Promise<void> {
      store.setTokenizer(NAME);
      store.setNumber('vocab_size', vocabulary);
      await settle();
      await pause();
      estimateRequest().flush(answer);
      await settle();
    }

    it('says the model is counted with the tokenizer vocabulary and keeps the typed one', async () => {
      await startUp();

      await typeIn(1000, estimate(RAISED, SIZE));

      expect(store.vocabularyNote()).toBe(
        'The tokenizer of \u2066Qwen/Qwen3-0.6B\u2069 has a vocabulary size of 151,936. The model is counted with that vocabulary.',
      );
      expect(store.blueprint().vocab_size).toBe(1000);
      expect(store.estimate()?.design.vocab_size).toBe(SIZE);
    });

    it('writes the same note in Arabic with the name kept whole', async () => {
      await startUp();
      locale.setLocale('ar');

      await typeIn(1000, estimate(RAISED, SIZE));

      expect(store.vocabularyNote()).toBe(ar.architect.vocabulary.raised.replace('{tokenizer}', '\u2066Qwen/Qwen3-0.6B\u2069').replace('{tokens}', '151,936'));
    });

    it('says nothing when the library does not know the tokenizer', async () => {
      await startUp();

      await typeIn(1000, estimate(DENSE_DESIGN, null));

      expect(store.vocabularyNote()).toBeNull();
    });

    it('says nothing when the typed vocabulary is already as large', async () => {
      await startUp();

      await typeIn(SIZE, estimate(RAISED, SIZE));

      expect(store.vocabularyNote()).toBeNull();
    });

    it('drops the note when the next answer no longer raises the vocabulary', async () => {
      await startUp();
      await typeIn(1000, estimate(RAISED, SIZE));
      expect(store.vocabularyNote()).not.toBeNull();

      store.setNumber('vocab_size', 200_000);
      await settle();
      await pause();
      estimateRequest().flush(estimate({ ...DENSE_DESIGN, vocab_size: 200_000 }, SIZE));
      await settle();

      expect(store.vocabularyNote()).toBeNull();
    });

    it('drops the note when the design is refused', async () => {
      await startUp();
      await typeIn(1000, estimate(RAISED, SIZE));

      store.setNumber('heads', 5);
      await settle();
      await pause();
      estimateRequest().flush(
        { error: { code: 'design_not_divisible', message: 'raw', fields: { heads: ['raw'] } } },
        { status: 400, statusText: 'Bad Request' },
      );
      await settle();

      expect(store.vocabularyNote()).toBeNull();
    });

    it('does not mark a saved design as changed because the answer raised its vocabulary', async () => {
      await startUp();
      await typeIn(1000, estimate(RAISED, SIZE));

      const saving = store.save({ name: 'Tiny', notes: '' });
      const request = backend.expectOne((r) => r.url === DRAFTS && r.method === 'POST');
      expect(request.request.body).toMatchObject({ tokenizer: NAME, design: { vocab_size: 1000 } });
      request.flush(draftWire('d1', { design: RAISED, tokenizer: NAME, tokenizer_vocabulary: SIZE }), {
        status: 201,
        statusText: 'Created',
      });
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1')]));
      await saving;

      expect(store.dirty()).toBe(false);
      expect(store.blueprint().vocab_size).toBe(1000);
      expect(store.trainBlocker()).toBeNull();
    });

    it('keeps the open design unchanged when it is renamed from the list', async () => {
      await startUp();
      await typeIn(1000, estimate(RAISED, SIZE));
      const saving = store.save({ name: 'Tiny', notes: '' });
      backend
        .expectOne((r) => r.url === DRAFTS && r.method === 'POST')
        .flush(draftWire('d1', { design: RAISED, tokenizer: NAME, tokenizer_vocabulary: SIZE }), {
          status: 201,
          statusText: 'Created',
        });
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1')]));
      await saving;
      const open = store.draft() ?? fail();

      const renaming = store.rename(open, { name: 'New name', notes: '' });
      backend
        .expectOne((r) => r.url === `${DRAFTS}d1/` && r.method === 'PATCH')
        .flush(draftWire('d1', { name: 'New name', design: RAISED, tokenizer: NAME, tokenizer_vocabulary: SIZE }));
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1')]));
      await renaming;

      expect(store.draft()?.name).toBe('New name');
      expect(store.dirty()).toBe(false);
    });
  });

  describe('saving', () => {
    it('stores a new design with its tokenizer and sizing', async () => {
      await startUp();
      store.setTokenizer(' trl-internal-testing/tiny-Qwen3ForCausalLM ');
      await settle();
      await pause();
      estimateRequest().flush(estimate());
      await settle();

      const saving = store.save({ name: 'Tiny', notes: 'for testing' });
      const request = backend.expectOne((r) => r.url === DRAFTS && r.method === 'POST');
      expect(request.request.body).toMatchObject({
        name: 'Tiny',
        notes: 'for testing',
        tokenizer: 'trl-internal-testing/tiny-Qwen3ForCausalLM',
        seq_len: 1024,
        batch: 8,
        design: { family: 'dense_decoder', layers: 12 },
      });
      request.flush(draftWire('d1', { name: 'Tiny' }), { status: 201, statusText: 'Created' });
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1')]));
      const result = await saving;

      expect('draft' in result && result.draft.id).toBe('d1');
      expect(store.draft()?.id).toBe('d1');
      expect(store.draftPage().results).toHaveLength(1);
      expect(store.saving()).toBe(false);
    });

    it('changes the saved design instead of adding another', async () => {
      await startUp();
      store.openDraft((await openable()) ?? fail());
      await settle();

      const saving = store.save({ name: 'Renamed', notes: '' });
      const request = backend.expectOne((r) => r.url === `${DRAFTS}d1/` && r.method === 'PATCH');
      expect(request.request.body).toMatchObject({ name: 'Renamed', tokenizer: 'trl-internal-testing/tiny-Qwen3ForCausalLM' });
      request.flush(draftWire('d1', { name: 'Renamed' }));
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1', { name: 'Renamed' })]));
      await saving;

      expect(store.draft()?.name).toBe('Renamed');
    });

    it('hands a refusal back to the dialog and keeps the design open', async () => {
      await startUp();

      const saving = store.save({ name: 'Tiny', notes: '' });
      backend
        .expectOne((r) => r.url === DRAFTS && r.method === 'POST')
        .flush({ error: { code: 'design_out_of_range', message: 'raw' } }, { status: 400, statusText: 'Bad Request' });
      const result = await saving;

      expect('error' in result && result.error.message).toBe(en.errors.design_out_of_range);
      expect(store.draft()).toBeNull();
      expect(store.saving()).toBe(false);
    });

    it('renames from the list without touching the editor', async () => {
      await startUp();
      const opened = (await openable()) ?? fail();
      store.openDraft(opened);
      store.setNumber('layers', 20);

      const renaming = store.rename(opened, { name: 'New name', notes: 'n' });
      const request = backend.expectOne((r) => r.url === `${DRAFTS}d1/` && r.method === 'PATCH');
      expect(request.request.body).toEqual({ name: 'New name', notes: 'n' });
      request.flush(draftWire('d1', { name: 'New name' }));
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1', { name: 'New name' })]));
      await renaming;

      expect(store.draft()?.name).toBe('New name');
      expect(store.blueprint().layers).toBe(20);
      expect(store.dirty()).toBe(true);
      await settle();
      await pause();
      estimateRequest().flush(estimate());
    });
  });

  describe('training', () => {
    it('needs a saved design, without unsaved changes, with a tokenizer', async () => {
      await startUp();
      expect(store.trainBlocker()).toBe('architect.train.needSaved');
      expect(store.canTrain()).toBe(false);

      const saved = (await openable()) ?? fail();
      store.openDraft(saved);
      expect(store.dirty()).toBe(false);
      expect(store.trainBlocker()).toBeNull();
      expect(store.canTrain()).toBe(true);

      store.setNumber('layers', 20);
      expect(store.dirty()).toBe(true);
      expect(store.trainBlocker()).toBe('architect.train.needSaving');

      store.setNumber('layers', saved.blueprint.layers);
      store.openDraft({ ...saved, blueprint: { ...saved.blueprint, tokenizer: '' } });
      store.setTokenizer('');
      expect(store.trainBlocker()).toBe('architect.train.needTokenizer');
      await settle();
      await pause();
      estimateRequest().flush(estimate());
    });

    it('lets only trainers and above write', async () => {
      await startUp(['viewers']);

      expect(store.canWrite()).toBe(false);
      expect(store.canSave()).toBe(false);
      expect(store.canTrain()).toBe(false);
    });

    it('starts the run with the projects chosen', async () => {
      await startUp();
      const saved = (await openable()) ?? fail();

      const training = store.train(saved, 'Mini', ['p1', 'p2'], [{ id: 'ds1', max_rows: 500 }, { id: 'ds2', max_rows: null }]);
      const request = backend.expectOne(`${DRAFTS}d1/train/`);
      expect(request.request.body).toEqual({
        name: 'Mini',
        corrections_from: ['p1', 'p2'],
        datasets: [
          { id: 'ds1', max_rows: 500 },
          { id: 'ds2', max_rows: null },
        ],
      });
      expect(store.training()).toBe(true);
      request.flush({ project: 'new-project', run: 'run-1' }, { status: 202, statusText: 'Accepted' });
      const result = await training;

      expect('started' in result && result.started).toEqual({ project: 'new-project', run: 'run-1' });
      expect(store.training()).toBe(false);
    });

    it('hands back why there was nothing to learn, in the reader language', async () => {
      await startUp();
      const saved = (await openable()) ?? fail();

      const training = store.train(saved, 'Mini', ['p1'], []);
      backend
        .expectOne(`${DRAFTS}d1/train/`)
        .flush({ error: { code: 'nothing_to_learn', message: 'raw' } }, { status: 409, statusText: 'Conflict' });
      const result = await training;

      expect('error' in result && result.error.code).toBe('nothing_to_learn');
      expect('error' in result && result.error.message).toBe(en.errors.nothing_to_learn);
    });

    it('hands back a dataset that is not ready, in the reader language', async () => {
      await startUp();
      const saved = (await openable()) ?? fail();

      const training = store.train(saved, 'Mini', [], [{ id: 'ds1', max_rows: null }]);
      backend
        .expectOne(`${DRAFTS}d1/train/`)
        .flush({ error: { code: 'dataset_not_ready', message: 'raw' } }, { status: 409, statusText: 'Conflict' });
      const result = await training;

      expect('error' in result && result.error.message).toBe(en.errors.dataset_not_ready);
    });

    it('counts approved replies for every project and keeps going when one count fails', async () => {
      await startUp();

      const loading = store.loadSources();
      backend
        .expectOne((r) => r.url === PROJECTS)
        .flush(page([{ id: 'p1', name: 'Support' }, { id: 'p2', name: 'Engine' }, { id: 'p3', name: 'Broken' }]));
      const library = backend.expectOne((r) => r.url === DATASETS);
      expect(library.request.params.get('page_size')).toBe('200');
      library.flush(
        page([
          { id: 'ds1', name: 'org/zen', status: 'ready', rows: 1200, has_thinking: true },
          { id: 'ds2', name: 'org/chat', status: 'importing', rows: 0, has_thinking: false },
        ]),
      );
      await vi.advanceTimersByTimeAsync(0);
      const plans = backend.match((r) => r.url === PLAN);
      expect(plans).toHaveLength(3);
      for (const plan of plans) {
        const project = plan.request.params.get('project');
        if (project === 'p1') {
          plan.flush({ corrections: 12 });
        } else if (project === 'p2') {
          plan.flush({ corrections: 0 });
        } else {
          plan.flush({ error: { code: 'unknown', message: 'x' } }, { status: 500, statusText: 'Server Error' });
        }
      }
      await loading;

      expect(store.sources()).toEqual([
        { id: 'p1', name: 'Support', corrections: 12 },
        { id: 'p2', name: 'Engine', corrections: 0 },
        { id: 'p3', name: 'Broken', corrections: null },
      ]);
      expect(store.datasets()).toEqual([{ id: 'ds1', name: 'org/zen', rows: 1200, hasThinking: true }]);
      expect(store.sourcesLoading()).toBe(false);
    });
  });

  describe('saved designs', () => {
    it('removes a design and closes it in the designer when it was open', async () => {
      await startUp();
      const saved = (await openable()) ?? fail();
      store.openDraft(saved);
      const loading = store.loadDrafts();
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1')], 1));
      await loading;

      const removing = store.removeDraft(saved);
      expect(store.working()).toEqual(['d1']);
      backend.expectOne((r) => r.url === `${DRAFTS}d1/` && r.method === 'DELETE').flush(null, {
        status: 204,
        statusText: 'No Content',
      });
      await vi.advanceTimersByTimeAsync(0);
      backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([]));
      expect(await removing).toBeNull();

      expect(store.draft()).toBeNull();
      expect(store.draftPage().results).toEqual([]);
      expect(store.working()).toEqual([]);
    });

    it('keeps the list and reports a failed removal', async () => {
      await startUp();
      const saved = (await openable()) ?? fail();

      const removing = store.removeDraft(saved);
      backend
        .expectOne((r) => r.method === 'DELETE')
        .flush({ error: { code: 'forbidden', message: 'No.' } }, { status: 400, statusText: 'Bad Request' });

      expect((await removing)?.code).toBe('forbidden');
      expect(store.working()).toEqual([]);
    });

    it('asks for the first page when the page opens', async () => {
      await startUp();

      const visiting = store.visit();
      const request = backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET');
      expect(request.request.params.get('page')).toBe('1');
      request.flush(page([draftWire('d1')]));
      await visiting;

      expect(store.draftPage().results.map((draft) => draft.name)).toEqual(['Design d1']);
      expect(store.draftPage().results[0].blueprint.tokenizer).toBe('trl-internal-testing/tiny-Qwen3ForCausalLM');
    });
  });

  async function openable() {
    const visiting = store.loadDrafts(0);
    backend.expectOne((r) => r.url === DRAFTS && r.method === 'GET').flush(page([draftWire('d1')]));
    await visiting;
    return store.draftPage().results.at(0);
  }

  function fail(): never {
    throw new Error('the saved design was not loaded');
  }
});
