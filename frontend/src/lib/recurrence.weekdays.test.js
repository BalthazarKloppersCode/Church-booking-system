import { describe, expect, it } from 'vitest';
import { countOccurrences, describeWeekdays, weekdayOf } from './recurrence';

// 23 Nov 2026 is a Monday.
describe('weekdayOf', () => {
  it('counts Monday as 0 and Sunday as 6', () => {
    expect(weekdayOf('2026-11-23')).toBe(0);
    expect(weekdayOf('2026-11-25')).toBe(2);
    expect(weekdayOf('2026-11-29')).toBe(6);
  });
});

describe('countOccurrences on chosen days', () => {
  it('counts Monday, Tuesday and Friday every week', () => {
    expect(countOccurrences('2026-11-23', '2026-12-04', 'weekly', [0, 1, 4])).toBe(6);
  });

  it('does not book a start day that is not ticked', () => {
    // Wed 25 Nov start; Mon + Fri: Fri 27, Mon 30, Fri 4, Mon 7
    expect(countOccurrences('2026-11-25', '2026-12-07', 'weekly', [0, 4])).toBe(4);
  });

  it('includes the until day', () => {
    expect(countOccurrences('2026-11-23', '2026-11-27', 'weekly', [0, 4])).toBe(2);
  });

  it('counts every second week', () => {
    expect(countOccurrences('2026-11-23', '2026-12-17', 'biweekly', [0, 3])).toBe(4);
  });

  it('is unchanged without chosen days, and for monthly', () => {
    expect(countOccurrences('2026-11-23', '2026-12-07', 'weekly')).toBe(3);
    expect(countOccurrences('2026-11-23', '2026-12-07', 'weekly', [])).toBe(3);
    expect(countOccurrences('2026-10-14', '2027-01-14', 'monthly', [0])).toBe(4);
  });

  it('stops counting at the server limit', () => {
    expect(countOccurrences('2026-01-05', '2030-01-05', 'weekly', [0, 1, 2, 3, 4, 5, 6])).toBeGreaterThan(104);
  });
});

describe('describeWeekdays', () => {
  it('reads like a sentence whatever order they were ticked in', () => {
    expect(describeWeekdays([4])).toBe('Friday');
    expect(describeWeekdays([4, 0])).toBe('Monday and Friday');
    expect(describeWeekdays([4, 1, 0])).toBe('Monday, Tuesday and Friday');
  });
});
