import { describe, expect, it } from 'vitest';

import type { Metric } from '../data/training.types';
import { readLoss } from './loss-trend';

function points(losses: readonly (number | null)[]): Metric[] {
  return losses.map((loss, index) => ({
    step: index + 1,
    epoch: null,
    loss,
    learning_rate: null,
    grad_norm: null,
  }));
}

describe('readLoss', () => {
  it('says it is too early with fewer than eight points', () => {
    expect(readLoss(points([]))).toEqual({ trend: 'too_early', first: null, latest: null });
    expect(readLoss(points([3, 2.8, 2.6, 2.4, 2.2, 2.0, 1.8]))).toEqual({ trend: 'too_early', first: 3, latest: 1.8 });
  });

  it('reads the trend from the eighth point on', () => {
    expect(readLoss(points([3, 2.8, 2.6, 2.4, 2.2, 2.0, 1.8, 1.6])).trend).toBe('falling');
  });

  it('reads a steady fall as learning', () => {
    const reading = readLoss(points([3.0, 2.8, 2.6, 2.4, 2.2, 2.0, 1.8, 1.6, 1.4]));

    expect(reading).toEqual({ trend: 'falling', first: 3.0, latest: 1.4 });
  });

  it('still reads a fall through noisy steps', () => {
    const reading = readLoss(points([2.5, 2.2, 2.4, 2.0, 2.1, 1.9, 1.8, 1.85, 1.7, 1.75, 1.6, 1.65]));

    expect(reading.trend).toBe('falling');
  });

  it('reads a flat last stretch as levelled off, even after a fall', () => {
    const reading = readLoss(points([4.0, 3.0, 2.2, 1.6, 1.2, 1.02, 1.0, 0.99, 1.0, 0.99, 1.0, 0.99]));

    expect(reading.trend).toBe('levelled_off');
    expect(reading.latest).toBe(0.99);
  });

  it('does not mistake noise around one level for a trend', () => {
    const reading = readLoss(points([1.0, 1.2, 0.9, 1.1, 1.0, 1.15, 0.95, 1.05, 1.1, 0.9, 1.0, 1.05]));

    expect(reading.trend).toBe('levelled_off');
  });

  it('reads a climb as getting worse', () => {
    const reading = readLoss(points([1.0, 1.0, 1.05, 1.2, 1.4, 1.7, 2.1, 2.6, 3.2]));

    expect(reading.trend).toBe('rising');
  });

  it('ignores steps with no loss', () => {
    const reading = readLoss(points([3.0, null, 2.8, 2.6, null, 2.4, 2.2, 2.0, 1.8, 1.6, 1.4]));

    expect(reading.trend).toBe('falling');
    expect(reading.first).toBe(3.0);
    expect(reading.latest).toBe(1.4);
  });

  it('treats a tiny wobble on a high loss as levelled off', () => {
    const reading = readLoss(points([11.93, 11.92, 11.93, 11.92, 11.93, 11.92, 11.93, 11.92, 11.93]));

    expect(reading.trend).toBe('levelled_off');
  });
});
