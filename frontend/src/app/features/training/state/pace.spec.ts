import { describe, expect, it } from 'vitest';

import { formatDuration, secondsLeft } from './pace';

describe('secondsLeft', () => {
  it('is unknown before two samples have moved', () => {
    expect(secondsLeft([], 30)).toBeNull();
    expect(secondsLeft([{ at: 0, step: 4 }], 30)).toBeNull();
    expect(
      secondsLeft(
        [
          { at: 0, step: 4 },
          { at: 4000, step: 4 },
        ],
        30,
      ),
    ).toBeNull();
  });

  it('divides the steps left by the recent rate', () => {
    const samples = [
      { at: 0, step: 2 },
      { at: 2000, step: 4 },
      { at: 4000, step: 6 },
    ];

    expect(secondsLeft(samples, 30)).toBe(24);
  });

  it('is zero when the last step is done', () => {
    expect(
      secondsLeft(
        [
          { at: 0, step: 28 },
          { at: 2000, step: 30 },
        ],
        30,
      ),
    ).toBe(0);
  });

  it('is unknown when the total is not known yet', () => {
    expect(
      secondsLeft(
        [
          { at: 0, step: 1 },
          { at: 1000, step: 2 },
        ],
        0,
      ),
    ).toBeNull();
  });
});

describe('formatDuration', () => {
  it('writes seconds, minutes and hours in the reader\'s language', () => {
    expect(formatDuration(45, 'en')).toBe('45 sec');
    expect(formatDuration(125, 'en')).toBe('2 min 5 sec');
    expect(formatDuration(3900, 'en')).toBe('1 hr 5 min');
    expect(formatDuration(45, 'ar')).toBe('45 ث');
    expect(formatDuration(125, 'ar')).toBe('2 د 5 ث');
  });

  it('never goes below zero', () => {
    expect(formatDuration(-3, 'en')).toBe('0 sec');
  });
});
