import { describe, expect, it } from 'vitest';

import { deviceOf } from './device';

describe('deviceOf', () => {
  it('knows the processor', () => {
    expect(deviceOf('cpu')).toEqual({ kind: 'cpu', index: null, raw: 'cpu' });
  });

  it('reads the GPU number', () => {
    expect(deviceOf('cuda:1')).toEqual({ kind: 'gpu', index: 1, raw: 'cuda:1' });
    expect(deviceOf('cuda')).toEqual({ kind: 'gpu', index: null, raw: 'cuda' });
  });

  it('keeps any other device as it was written', () => {
    expect(deviceOf('mps')).toEqual({ kind: 'other', index: null, raw: 'mps' });
  });

  it('says nothing when no device is reported', () => {
    expect(deviceOf(null).kind).toBe('none');
    expect(deviceOf('').kind).toBe('none');
  });
});
