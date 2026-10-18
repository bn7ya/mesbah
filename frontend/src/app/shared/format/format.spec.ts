import { describe, expect, it } from 'vitest';

import { formatBytes, formatCompact, formatDateTime, formatNumber, formatPercent, formatSignificant } from './format';

const GIB = 1024 ** 3;

function plain(text: string): string {
  return text.replace(/[\u2066\u2069]/g, '');
}

describe('formatBytes', () => {
  it('names a 16 GB card the way its box does', () => {
    expect(plain(formatBytes(16 * GIB, 'en'))).toBe('16 GB');
  });

  it('keeps one decimal below ten', () => {
    expect(plain(formatBytes(1.5 * GIB, 'en'))).toBe('1.5 GB');
  });

  it('uses Latin digits in Arabic too', () => {
    expect(plain(formatBytes(16 * GIB, 'ar'))).toBe('16 GB');
  });

  it('keeps the number before its unit in an Arabic sentence', () => {
    expect(formatBytes(16 * GIB, 'ar')).toBe('\u206616 GB\u2069');
  });

  it('never shows a negative size', () => {
    expect(plain(formatBytes(-5, 'en'))).toBe('0 B');
  });
});

describe('formatNumber', () => {
  it('groups thousands', () => {
    expect(formatNumber(14_000_000_000, 'en')).toBe('14,000,000,000');
  });
});

describe('formatCompact', () => {
  it('shortens a model size to billions', () => {
    expect(formatCompact(8_190_735_360, 'en')).toBe('8.2B');
  });

  it('shortens a download count to millions', () => {
    expect(formatCompact(9_122_623, 'en')).toBe('9.1M');
  });

  it('leaves a small count whole', () => {
    expect(formatCompact(999, 'en')).toBe('999');
  });

  it('writes the unit in Arabic with Latin digits', () => {
    expect(formatCompact(8_190_735_360, 'ar')).toBe('8.2\u00a0مليار');
  });
});

describe('formatSignificant', () => {
  it('keeps two significant digits of a small number', () => {
    expect(formatSignificant(0.012345, 'en')).toBe('0.012');
  });

  it('rounds a large number to two significant digits', () => {
    expect(formatSignificant(1234.5, 'en')).toBe('1,200');
  });

  it('uses Latin digits in Arabic', () => {
    expect(formatSignificant(0.82, 'ar')).toBe('0.82');
  });
});

describe('formatPercent', () => {
  it('keeps one decimal below ten percent', () => {
    expect(plain(formatPercent(0.0534, 'en'))).toBe('5.3%');
  });

  it('rounds from ten percent up', () => {
    expect(plain(formatPercent(0.347, 'en'))).toBe('35%');
  });

  it('keeps the number before its sign in an Arabic sentence', () => {
    expect(formatPercent(0.5, 'ar')).toBe('\u206650%\u2069');
  });
});

describe('formatDateTime', () => {
  it('writes the day and the time in the reader\'s language with Latin digits', () => {
    expect(formatDateTime('2026-10-18T14:30:00Z', 'en')).toMatch(/2026/);
    expect(formatDateTime('2026-10-18T14:30:00Z', 'ar')).toMatch(/2026/);
  });
});
