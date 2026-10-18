import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { EMPTY } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { UiModeStore } from '@core/ui/ui-mode.store';
import type { LossReading, Metric, Run, SourceNames, VersionSize } from '../../data/training.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { RunStore } from '../../state/run.store';
import { RunPage } from './run';

const LORA: Run = {
  id: 'r1',
  project: 'p1',
  kind: 'lora',
  draft: null,
  corrections_from: [],
  name: 'Friendlier',
  notes: '',
  starts_from: { id: 'v1', name: 'First', number: 1 },
  version: { id: 'v2', name: 'Friendlier', number: 2 },
  use_corrections: true,
  datasets: [],
  hyperparams: {
    epochs: 2,
    learning_rate: 2e-4,
    lora_rank: 16,
    lora_alpha: 32,
    lora_dropout: 0,
    max_seq_len: 2048,
    batch_size: 1,
    grad_accum: 8,
    quantize_4bit: false,
    gradient_checkpointing: true,
  },
  activate_when_done: true,
  status: 'completed',
  stage: 'training',
  examples: 4,
  skipped: 0,
  tokens: 900,
  step: 30,
  total_steps: 30,
  epoch: 2,
  loss: 0.8,
  max_seq_len: null,
  gpu_indices: [],
  error_code: '',
  error_detail: '',
  cancel_requested: false,
  started_at: '2026-10-18T10:00:00Z',
  finished_at: '2026-10-18T10:01:30Z',
  created_at: '2026-10-18T09:59:00Z',
  created_by: 'tariq',
};

const NEW_MODEL: Run = {
  ...LORA,
  kind: 'pretrain',
  draft: 'dr1',
  corrections_from: ['pa', 'pb'],
  name: 'base',
  starts_from: null,
  version: { id: 'v0', name: 'base', number: 0 },
  use_corrections: false,
  hyperparams: {
    epochs: 1,
    learning_rate: 3e-4,
    max_seq_len: 1024,
    batch_size: 8,
    grad_accum: 1,
    warmup_ratio: 0.03,
    gradient_checkpointing: true,
    quantize_4bit: false,
    pretrain: { optim: 'adamw_8bit' },
  },
  datasets: [{ id: 'd1', name: 'Stories', rows: 40, max_rows: null }],
};

describe('RunPage', () => {
  const current = signal<Run | null>(null);
  const size = signal<VersionSize | null>(null);
  const sourceNames = signal<SourceNames | null>(null);
  let fixture: ReturnType<typeof TestBed.createComponent<RunPage>>;

  function render(item: Run, locale: 'en' | 'ar' = 'en'): HTMLElement {
    current.set(item);
    TestBed.inject(LocaleStore).setLocale(locale);
    fixture = TestBed.createComponent(RunPage);
    fixture.componentRef.setInput('projectId', 'p1');
    fixture.componentRef.setInput('runId', item.id);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  function section(page: HTMLElement, id: string): string {
    return page.querySelector(`[aria-labelledby="${id}"]`)?.textContent ?? '';
  }

  beforeEach(() => {
    localStorage.clear();
    size.set(null);
    sourceNames.set(null);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: RunStore,
          useValue: {
            run: current,
            points: signal<readonly Metric[]>([]),
            loading: signal(false),
            error: signal<ApiError | null>(null),
            finished: signal(true),
            canStop: signal(false),
            stopping: signal(false),
            stopError: signal<ApiError | null>(null),
            progress: signal(100),
            reading: signal<LossReading>({ trend: 'too_early', first: null, latest: null }),
            elapsedSeconds: signal(90),
            remainingSeconds: signal<number | null>(null),
            size,
            sourceNames,
            open: () => undefined,
            watch: () => EMPTY,
          },
        },
      ],
    });
    TestBed.inject(LocaleStore).register({ en, ar });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  describe('a finished LoRA run', () => {
    it('says it started from a version and shows how small the change is', () => {
      size.set({ sizeBytes: 84_000_000, fullSizeBytes: 16_000_000_000 });
      const page = render(LORA);

      expect(page.querySelector('h2')?.textContent).toBe('Friendlier');
      expect(page.querySelector('.run__facts')?.textContent).toContain('Started from');
      const result = section(page, 'run-result');
      expect(result).toContain('Training is done and the version is saved.');
      expect(result).toContain('Size of the change');
      expect(result).toContain('of the full model');
      expect(result).not.toContain('joined the library');
      expect(page.querySelector('a[href="/models"]')).toBeNull();
    });

    it('lists its approved replies as used, and its rank among the settings', () => {
      TestBed.inject(UiModeStore).setMode('expert');
      const page = render(LORA);

      expect(section(page, 'run-learns')).toContain('Used');
      expect(section(page, 'run-learns')).not.toContain('Approved replies from');
      const used = section(page, 'run-settings');
      expect(used).toContain('LoRA rank');
      expect(used).toContain('LoRA alpha');
      expect(used).not.toContain('Optimizer');
    });
  });

  describe('a finished run that trained a new model', () => {
    it('says it was trained from nothing, under a title that names it', () => {
      const page = render(NEW_MODEL);

      expect(page.querySelector('h2')?.textContent).toBe('New model');
      const facts = page.querySelector('.run__facts')?.textContent ?? '';
      expect(facts).toContain('A new model, trained from nothing');
      expect(facts).not.toContain('Started from');
    });

    it('says the model joined the library and is now the base, without a size', () => {
      size.set({ sizeBytes: 0, fullSizeBytes: 31_000_000 });
      const page = render(NEW_MODEL);

      const result = section(page, 'run-result');
      expect(result).toContain('Training is done and the new model is saved.');
      expect(result).toContain("The model joined the library and is now this project's base model.");
      expect(result).toContain('First version');
      expect(result).toContain('v0');
      expect(result).not.toContain('Size of the change');
      expect(result).not.toContain('of the full model');
      expect(result).not.toContain('Active version');
    });

    it('links to the chat of the project and to the models page', () => {
      const page = render(NEW_MODEL);

      expect(page.querySelector('a[href="/projects/p1/chat"]')?.textContent).toContain('Go to Chat');
      expect(page.querySelector('a[href="/models"]')?.textContent).toContain('Go to Models');
      expect(page.querySelector('a[href="/projects/p1/versions"]')?.textContent).toContain('v0');
    });

    it('counts the projects it learns from until their names are known, then names them', () => {
      const page = render(NEW_MODEL);

      expect(section(page, 'run-learns')).toContain('Approved replies from');
      expect(section(page, 'run-learns')).toContain('Projects: 2');
      expect(section(page, 'run-learns')).not.toContain('Used');

      sourceNames.set({ pa: 'Support' });
      fixture.detectChanges();

      const learns = section(page, 'run-learns');
      expect(learns).toContain('Support');
      expect(learns).toContain('A removed project');
      expect(learns).toContain('Stories');
      expect(learns).not.toContain('Projects: 2');
      expect(page.querySelector('a[href="/projects/pa/training"]')?.textContent).toBe('Support');
    });

    it('shows the optimizer by name in Simple mode, and no LoRA setting in Expert mode', () => {
      const simple = section(render(NEW_MODEL), 'run-settings');
      expect(simple).toContain('Optimizer');
      expect(simple).toContain('8-bit Adam');
      expect(simple).not.toContain('LoRA');
      expect(simple).not.toContain('Warm-up share');
    });

    it('shows its warm-up and the rest of its settings in Expert mode, never a LoRA one', () => {
      TestBed.inject(UiModeStore).setMode('expert');
      const used = section(render(NEW_MODEL), 'run-settings');

      expect(used).toContain('Warm-up share');
      expect(used).toContain('0.03');
      expect(used).toContain('Examples per step');
      expect(used).not.toContain('LoRA');
      expect(used).not.toContain('Rank-stabilised');
      expect(used).not.toContain('Train biases');
    });

    it('says the same in Arabic', () => {
      const page = render(NEW_MODEL, 'ar');

      expect(page.querySelector('h2')?.textContent).toBe('نموذج جديد');
      expect(section(page, 'run-result')).toContain('تمت إضافة النموذج إلى المكتبة');
      expect(section(page, 'run-learns')).toContain('الردود المعتمدة من');
      expect(section(page, 'run-settings')).toContain('خوارزمية التحسين');
    });
  });

  describe('a failed run that trained a new model', () => {
    it('gives advice that fits a new model, not a smaller rank', () => {
      const page = render({ ...NEW_MODEL, status: 'failed', version: null, error_code: 'out_of_memory' });

      const result = section(page, 'run-result');
      expect(result).toContain('Design a smaller model in the Architect');
      expect(result).not.toContain('rank');
    });

    it('keeps the plain wording for a failure that reads the same for both', () => {
      const page = render({ ...NEW_MODEL, status: 'failed', version: null, error_code: 'something_else' });

      expect(section(page, 'run-result')).toContain('Training failed.');
    });
  });
});
