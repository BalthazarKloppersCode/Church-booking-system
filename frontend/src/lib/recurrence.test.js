import { describe, expect, it } from 'vitest';
import { addMonths, countOccurrences, defaultUntil } from './recurrence';

describe('countOccurrences', () => {
  it('counts the first booking plus every repeat up to and including the until date', () => {
    expect(countOccurrences('2026-10-14', '2026-10-14', 'weekly')).toBe(1);
    expect(countOccurrences('2026-10-14', '2026-10-20', 'weekly')).toBe(1);
    expect(countOccurrences('2026-10-14', '2026-10-21', 'weekly')).toBe(2);
    expect(countOccurrences('2026-10-14', '2026-12-30', 'weekly')).toBe(12);
  });

  it('steps two weeks or a month at a time', () => {
    expect(countOccurrences('2026-10-14', '2026-12-30', 'biweekly')).toBe(6);
    expect(countOccurrences('2026-10-14', '2027-01-14', 'monthly')).toBe(4);
  });

  it('returns to the 31st after a short month instead of drifting', () => {
    // 31 Jan, 28 Feb, 31 Mar, 30 Apr
    expect(countOccurrences('2027-01-31', '2027-04-30', 'monthly')).toBe(4);
  });

  it('stops at the server limit rather than looping for ever', () => {
    expect(countOccurrences('2026-01-01', '2099-01-01', 'weekly')).toBeGreaterThan(104);
  });
});

describe('defaultUntil', () => {
  it('is three months after the first booking, so a repeat is never a single booking by default', () => {
    expect(defaultUntil('2026-10-14')).toBe('2027-01-14');
    expect(defaultUntil('2026-11-30')).toBe('2027-02-28');
    expect(countOccurrences('2026-10-14', defaultUntil('2026-10-14'), 'weekly')).toBeGreaterThan(10);
  });
});

describe('addMonths', () => {
  it('clamps to the last day of a shorter month', () => {
    expect(addMonths(new Date(2027, 0, 31), 1).getDate()).toBe(28);
    expect(addMonths(new Date(2026, 11, 15), 2).getFullYear()).toBe(2027);
  });
});
