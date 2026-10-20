import { describe, expect, it } from 'vitest';

import { FALLBACK_SETTINGS, type Hyperparams, type Plan } from '../data/training.types';
import { expertChanged, problemsOf, resetExpert, settingsFrom } from './train-settings';

const PLAN: Plan = {
  hyperparams: { epochs: 3, max_seq_len: 4096, quantize_4bit: true },
  corrections: 5,
  fit: { verdict: 'fits', required_bytes: 1, available_bytes: 2 },
  gpu_indices: [0],
};

describe('settingsFrom', () => {
  it('lays the plan over the fallbacks', () => {
    const settings = settingsFrom(PLAN);

    expect(settings.epochs).toBe(3);
    expect(settings.max_seq_len).toBe(4096);
    expect(settings.quantize_4bit).toBe(true);
    expect(settings.lora_rank).toBe(FALLBACK_SETTINGS.lora_rank);
  });

  it('uses the fallbacks before the plan has loaded', () => {
    expect(settingsFrom(null)).toEqual(FALLBACK_SETTINGS);
  });
});

describe('problemsOf', () => {
  it('finds nothing wrong with the defaults', () => {
    expect(problemsOf(FALLBACK_SETTINGS)).toEqual([]);
  });

  it('flags a value out of range, a fraction where a whole number is needed and an empty required field', () => {
    const settings = {
      ...FALLBACK_SETTINGS,
      batch_size: 100,
      grad_accum: 1.5,
      learning_rate: null as unknown as number,
    } satisfies Hyperparams;

    expect(problemsOf(settings)).toEqual([
      { key: 'learning_rate', kind: 'required' },
      { key: 'batch_size', kind: 'range' },
      { key: 'grad_accum', kind: 'whole' },
    ]);
  });

  it('accepts an empty step limit and refuses one below 1', () => {
    expect(problemsOf({ ...FALLBACK_SETTINGS, max_steps: null })).toEqual([]);
    expect(problemsOf({ ...FALLBACK_SETTINGS, max_steps: 0 })).toEqual([{ key: 'max_steps', kind: 'range' }]);
  });
});

describe('expertChanged and resetExpert', () => {
  it('notices an expert-only setting that differs and puts it back', () => {
    const changed = { ...FALLBACK_SETTINGS, max_steps: 30, use_rslora: true, epochs: 4 };

    expect(expertChanged(FALLBACK_SETTINGS, FALLBACK_SETTINGS)).toBe(false);
    expect(expertChanged(changed, FALLBACK_SETTINGS)).toBe(true);

    const reset = resetExpert(changed, FALLBACK_SETTINGS);
    expect(expertChanged(reset, FALLBACK_SETTINGS)).toBe(false);
    expect(reset.epochs).toBe(4);
  });

  it('does not count the three simple settings as expert ones', () => {
    expect(expertChanged({ ...FALLBACK_SETTINGS, epochs: 5, learning_rate: 5e-4, lora_rank: 64 }, FALLBACK_SETTINGS)).toBe(false);
  });
});
