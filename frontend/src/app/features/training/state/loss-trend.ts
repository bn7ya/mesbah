import { LOSS_FALL, LOSS_MIN_POINTS, LOSS_RISE, type LossReading, type Metric } from '../data/training.types';

const WINDOW_MIN = 2;
const WINDOW_MAX = 20;
const SIGNIFICANCE = 2;

function mean(values: readonly number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function varianceOfMean(values: readonly number[], average: number): number {
  const spread = values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1);
  return spread / values.length;
}

export function readLoss(points: readonly Metric[]): LossReading {
  const losses = points.map((point) => point.loss).filter((loss): loss is number => loss !== null && Number.isFinite(loss));
  const first = losses[0] ?? null;
  const latest = losses.at(-1) ?? null;
  if (losses.length < LOSS_MIN_POINTS) {
    return { trend: 'too_early', first, latest };
  }

  const window = Math.min(WINDOW_MAX, Math.max(WINDOW_MIN, Math.floor(losses.length / 3)));
  const recent = losses.slice(-window);
  const before = losses.slice(-2 * window, -window);
  const recentMean = mean(recent);
  const beforeMean = mean(before);
  const change = recentMean - beforeMean;
  const noise = Math.sqrt(varianceOfMean(recent, recentMean) + varianceOfMean(before, beforeMean));
  const clear = Math.abs(change) > SIGNIFICANCE * noise;
  const relative = beforeMean === 0 ? 0 : change / Math.abs(beforeMean);

  if (clear && relative >= LOSS_RISE) {
    return { trend: 'rising', first, latest };
  }
  if (clear && relative <= -LOSS_FALL) {
    return { trend: 'falling', first, latest };
  }
  return { trend: 'levelled_off', first, latest };
}
