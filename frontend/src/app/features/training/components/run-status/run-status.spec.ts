import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import type { Run, RunKind, RunStage, RunStatus } from '../../data/training.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { RunStatus as RunStatusView } from './run-status';

function run(kind: RunKind, status: RunStatus, stage: RunStage = ''): Run {
  return {
    id: 'r1',
    project: 'p1',
    kind,
    draft: kind === 'pretrain' ? 'dr1' : null,
    corrections_from: [],
    name: 'base',
    notes: '',
    starts_from: kind === 'pretrain' ? null : { id: 'v1', name: 'First', number: 1 },
    version: null,
    use_corrections: kind === 'lora',
    datasets: [],
    hyperparams: {},
    activate_when_done: true,
    status,
    stage,
    examples: null,
    skipped: null,
    tokens: null,
    step: 0,
    total_steps: 0,
    epoch: null,
    loss: null,
    max_seq_len: null,
    gpu_indices: [],
    error_code: '',
    error_detail: '',
    cancel_requested: false,
    started_at: null,
    finished_at: null,
    created_at: '2026-10-18T10:00:00Z',
    created_by: 'tariq',
  };
}

describe('RunStatus', () => {
  function words(item: Run, locale: 'en' | 'ar' = 'en'): string {
    const store = TestBed.inject(LocaleStore);
    store.register({ en, ar });
    store.setLocale(locale);
    const fixture = TestBed.createComponent(RunStatusView);
    fixture.componentRef.setInput('run', item);
    fixture.detectChanges();
    return (fixture.nativeElement as HTMLElement).textContent?.trim() ?? '';
  }

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('says a LoRA run is loading the model and then saving the change', () => {
    expect(words(run('lora', 'preparing', 'model'))).toBe('Loading the model');
    expect(words(run('lora', 'preparing', 'parent'))).toBe('Starting from v1');
    expect(words(run('lora', 'saving'))).toBe('Saving the change');
  });

  it('says a new model is loading the tokenizer, building the model and saving the model', () => {
    expect(words(run('pretrain', 'preparing', 'data'))).toBe('Preparing the examples');
    expect(words(run('pretrain', 'preparing', 'tokenizer'))).toBe('Loading the tokenizer');
    expect(words(run('pretrain', 'preparing', 'model'))).toBe('Building the model');
    expect(words(run('pretrain', 'saving'))).toBe('Saving the model');
  });

  it('says the same for a new model in Arabic', () => {
    expect(words(run('pretrain', 'preparing', 'model'), 'ar')).toBe('بناء النموذج');
    expect(words(run('pretrain', 'saving'), 'ar')).toBe('حفظ النموذج');
  });

  it('says a step count for either kind while it learns', () => {
    const learning = { ...run('pretrain', 'training', 'training'), step: 3, total_steps: 30 };

    expect(words(learning)).toBe('Learning: step 3 of 30');
  });
});
