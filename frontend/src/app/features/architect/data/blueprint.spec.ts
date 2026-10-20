import { describe, expect, it } from 'vitest';

import { DEFAULT_BLUEPRINT, type Blueprint, type Design } from './architect.types';
import { blueprintOf, designRequest, estimateRequest, raisedVocabulary, signature, withinLimit } from './blueprint';

const DENSE: Design = {
  family: 'dense_decoder',
  layers: 2,
  hidden_size: 64,
  heads: 4,
  kv_heads: 2,
  intermediate_size: 256,
  vocab_size: 32000,
  context_length: 256,
  experts: 0,
  experts_per_token: 0,
  encoder_layers: 0,
  decoder_layers: 0,
  tie_embeddings: true,
};

describe('blueprint', () => {
  it('fills the fields a family does not use with editable defaults', () => {
    const blueprint = blueprintOf(DENSE, { tokenizer: 'Qwen/Qwen3-0.6B', seq_len: 512, batch: 4 });

    expect(blueprint.layers).toBe(2);
    expect(blueprint.experts).toBe(DEFAULT_BLUEPRINT.experts);
    expect(blueprint.encoder_layers).toBe(DEFAULT_BLUEPRINT.encoder_layers);
    expect(blueprint.tokenizer).toBe('Qwen/Qwen3-0.6B');
    expect(blueprint.seq_len).toBe(512);
  });

  it('keeps an empty key-value head count as no sharing', () => {
    expect(blueprintOf({ ...DENSE, kv_heads: null }, { tokenizer: '', seq_len: 64, batch: 1 }).kv_heads).toBeNull();
  });

  it('sends a decoder its layers and key-value heads, and nothing for experts', () => {
    const request = designRequest({ ...DEFAULT_BLUEPRINT, family: 'dense_decoder' });

    expect(request).toMatchObject({ family: 'dense_decoder', layers: 12, kv_heads: 4, tie_embeddings: true });
    expect(request).not.toHaveProperty('experts');
    expect(request).not.toHaveProperty('encoder_layers');
  });

  it('sends a mixture of experts its experts', () => {
    const request = designRequest({ ...DEFAULT_BLUEPRINT, family: 'moe_decoder' });

    expect(request).toMatchObject({ experts: 8, experts_per_token: 2, layers: 12 });
  });

  it('sends an encoder-decoder its two stacks, always sharing the vocabulary table', () => {
    const request = designRequest({ ...DEFAULT_BLUEPRINT, family: 'encoder_decoder', tie_embeddings: false });

    expect(request).toMatchObject({ encoder_layers: 6, decoder_layers: 6, tie_embeddings: true });
    expect(request).not.toHaveProperty('layers');
    expect(request).not.toHaveProperty('kv_heads');
  });

  it('builds no estimate request while the sequence length or batch is out of range', () => {
    expect(estimateRequest(DEFAULT_BLUEPRINT)).toMatchObject({ seq_len: 1024, batch: 8 });
    expect(estimateRequest({ ...DEFAULT_BLUEPRINT, seq_len: 63 })).toBeNull();
    expect(estimateRequest({ ...DEFAULT_BLUEPRINT, batch: null })).toBeNull();
    expect(estimateRequest({ ...DEFAULT_BLUEPRINT, batch: 1.5 })).toBeNull();
  });

  it('sends the tokenizer without the spaces around it', () => {
    expect(estimateRequest({ ...DEFAULT_BLUEPRINT, tokenizer: ' Qwen/Qwen3-0.6B ' })?.tokenizer).toBe('Qwen/Qwen3-0.6B');
    expect(estimateRequest(DEFAULT_BLUEPRINT)?.tokenizer).toBe('');
  });

  it('finds a vocabulary raised to the tokenizer only when the tokenizer is larger', () => {
    const request = estimateRequest({ ...DEFAULT_BLUEPRINT, tokenizer: 'Qwen/Qwen3-0.6B', vocab_size: 1000 });
    if (request === null) {
      throw new Error('the request was not built');
    }

    expect(raisedVocabulary(request, 151_936)).toEqual({ tokenizer: 'Qwen/Qwen3-0.6B', tokens: 151_936 });
    expect(raisedVocabulary(request, 1000)).toBeNull();
    expect(raisedVocabulary(request, 512)).toBeNull();
    expect(raisedVocabulary(request, null)).toBeNull();
  });

  it('accepts only whole numbers inside the limits', () => {
    expect(withinLimit(64, 'seq_len')).toBe(true);
    expect(withinLimit(131_072, 'seq_len')).toBe(true);
    expect(withinLimit(131_073, 'seq_len')).toBe(false);
    expect(withinLimit(null, 'batch')).toBe(false);
  });

  it('ignores the fields a family does not use when comparing, and the spaces around a tokenizer', () => {
    const base: Blueprint = { ...DEFAULT_BLUEPRINT, tokenizer: 'a/b' };

    expect(signature({ ...base, experts: 64, encoder_layers: 9 })).toBe(signature(base));
    expect(signature({ ...base, tokenizer: ' a/b ' })).toBe(signature(base));
    expect(signature({ ...base, layers: 13 })).not.toBe(signature(base));
    expect(signature({ ...base, family: 'moe_decoder' })).not.toBe(signature(base));
  });
});
