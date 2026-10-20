import { describe, expect, it } from 'vitest';

import type { RunHyperparams } from '../data/training.types';
import { settingValue, shownSettings } from './run-settings';

const LORA: RunHyperparams = {
  epochs: 2,
  learning_rate: 2e-4,
  lora_rank: 16,
  lora_alpha: 32,
  lora_dropout: 0,
  use_rslora: false,
  train_biases: false,
  max_seq_len: 2048,
  batch_size: 1,
  grad_accum: 8,
  quantize_4bit: false,
  gradient_checkpointing: true,
};

const NEW_MODEL: RunHyperparams = {
  epochs: 1,
  learning_rate: 3e-4,
  max_seq_len: 1024,
  batch_size: 8,
  grad_accum: 1,
  warmup_ratio: 0.03,
  gradient_checkpointing: true,
  quantize_4bit: false,
  pretrain: { optim: 'adamw_8bit' },
};

describe('shownSettings', () => {
  it('shows the passes, the rank and the rate of a LoRA run in Simple mode', () => {
    expect(shownSettings(LORA, false)).toEqual(['epochs', 'learning_rate', 'lora_rank']);
  });

  it('shows every setting a LoRA run has in Expert mode, and no pretrain setting', () => {
    const keys = shownSettings(LORA, true);

    expect(keys).toContain('lora_alpha');
    expect(keys).toContain('use_rslora');
    expect(keys).not.toContain('optim');
    expect(keys).not.toContain('warmup_ratio');
  });

  it('shows the optimizer instead of the rank for a new model in Simple mode', () => {
    expect(shownSettings(NEW_MODEL, false)).toEqual(['epochs', 'learning_rate', 'optim']);
  });

  it('shows only the settings a new model has in Expert mode', () => {
    expect(shownSettings(NEW_MODEL, true)).toEqual([
      'epochs',
      'learning_rate',
      'optim',
      'max_seq_len',
      'batch_size',
      'grad_accum',
      'warmup_ratio',
      'quantize_4bit',
      'gradient_checkpointing',
    ]);
  });

  it('shows nothing for a run that has no settings yet', () => {
    expect(shownSettings({}, true)).toEqual([]);
  });
});

describe('settingValue', () => {
  it('reads the optimizer from the pretrain settings', () => {
    expect(settingValue(NEW_MODEL, 'optim')).toBe('adamw_8bit');
    expect(settingValue(LORA, 'optim')).toBeUndefined();
  });

  it('reads the other settings from the top level', () => {
    expect(settingValue(NEW_MODEL, 'warmup_ratio')).toBe(0.03);
    expect(settingValue(NEW_MODEL, 'lora_rank')).toBeUndefined();
  });
});
