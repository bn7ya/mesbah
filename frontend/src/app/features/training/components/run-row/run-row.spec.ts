import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import type { Run, SourceNames } from '../../data/training.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { TrainingStore } from '../../state/training.store';
import { RunRow } from './run-row';

function run(overrides: Partial<Run> = {}): Run {
  return {
    id: 'r1',
    project: 'p1',
    kind: 'lora',
    draft: null,
    corrections_from: [],
    name: 'Friendlier',
    notes: '',
    starts_from: { id: 'v1', name: 'First', number: 1 },
    version: null,
    use_corrections: true,
    datasets: [],
    hyperparams: {},
    activate_when_done: true,
    status: 'training',
    stage: 'training',
    examples: 4,
    skipped: 0,
    tokens: 900,
    step: 3,
    total_steps: 30,
    epoch: null,
    loss: null,
    max_seq_len: null,
    gpu_indices: [],
    error_code: '',
    error_detail: '',
    cancel_requested: false,
    started_at: '2026-10-18T10:00:00Z',
    finished_at: null,
    created_at: '2026-10-18T09:59:00Z',
    created_by: 'tariq',
    ...overrides,
  };
}

const NEW_MODEL: Partial<Run> = {
  kind: 'pretrain',
  draft: 'dr1',
  name: 'base',
  starts_from: null,
  use_corrections: false,
  corrections_from: ['pa', 'pb'],
};

describe('RunRow', () => {
  const sourceNames = signal<SourceNames | null>(null);
  let fixture: ReturnType<typeof TestBed.createComponent<RunRow>>;

  function render(item: Run, locale: 'en' | 'ar' = 'en'): HTMLElement {
    TestBed.inject(LocaleStore).setLocale(locale);
    fixture = TestBed.createComponent(RunRow);
    fixture.componentRef.setInput('run', item);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(() => {
    localStorage.clear();
    sourceNames.set(null);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: TrainingStore,
          useValue: {
            projectId: signal('p1'),
            canWrite: signal(true),
            working: signal<readonly string[]>([]),
            stopping: signal<readonly string[]>([]),
            sourceNames,
          },
        },
      ],
    });
    TestBed.inject(LocaleStore).register({ en, ar });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('says a LoRA run started from a version, under the name it was given', () => {
    const row = render(run());

    expect(row.querySelector('h3')?.textContent).toBe('Friendlier');
    expect(row.textContent).toContain('Started from');
    expect(row.textContent).toContain('v1');
    expect(row.textContent).not.toContain('trained from nothing');
    expect(row.textContent).not.toContain('Approved replies from');
  });

  it('says a new model is trained from nothing, and never shows its seeded name', () => {
    const row = render(run(NEW_MODEL));

    expect(row.querySelector('h3')?.textContent).toBe('New model');
    expect(row.textContent).toContain('A new model, trained from nothing');
    expect(row.textContent).not.toContain('Started from');
    expect(row.textContent).not.toContain('base');
  });

  it('counts the projects it learns from until their names are known', () => {
    const row = render(run(NEW_MODEL));

    expect(row.textContent).toContain('Approved replies from');
    expect(row.textContent).toContain('Projects: 2');

    sourceNames.set({ pa: 'Support', pb: 'Engine check' });
    fixture.detectChanges();

    expect(row.textContent).toContain('Support, Engine check');
    expect(row.textContent).not.toContain('Projects: 2');
  });

  it('names a project that was removed in words', () => {
    sourceNames.set({ pa: 'Support' });
    const row = render(run(NEW_MODEL));

    expect(row.textContent).toContain('Support, A removed project');
  });

  it('leaves out the projects line when a new model learns from datasets alone', () => {
    const row = render(run({ ...NEW_MODEL, corrections_from: [], datasets: [{ id: 'd1', name: 'Stories', rows: 40, max_rows: null }] }));

    expect(row.textContent).not.toContain('Approved replies from');
    expect(row.textContent).toContain('Stories');
  });

  it('links the version a new model made to the versions page', () => {
    const row = render(run({ ...NEW_MODEL, status: 'completed', version: { id: 'v0', name: 'base', number: 0 } }));

    expect(row.querySelector('a[href="/projects/p1/versions"]')?.textContent).toContain('v0');
  });

  it('says the same in Arabic', () => {
    const row = render(run(NEW_MODEL), 'ar');

    expect(row.querySelector('h3')?.textContent).toBe('نموذج جديد');
    expect(row.textContent).toContain('نموذج جديد يتدرب من الصفر');
    expect(row.textContent).toContain('عدد المشاريع: 2');

    sourceNames.set({ pa: 'Support', pb: 'Engine check' });
    fixture.detectChanges();

    expect(row.textContent).toContain('Support، Engine check');
  });
});
