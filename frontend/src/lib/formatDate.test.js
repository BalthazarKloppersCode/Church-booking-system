import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';
import {
  formatDateRange,
  formatDay,
  formatDayLong,
  formatDayShort,
  formatRelative,
  formatSlot,
  formatTime,
  formatTimeRange,
} from './formatDate';

// DESIGN_DIRECTION.md was sampled "on 1 Oct 2026" and its §7 before/after
// table is written against that date — pin "now" to match so formatRelative
// and the year-omission rule are deterministic.
beforeAll(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 9, 1, 12, 0, 0)); // 1 Oct 2026, 12:00 local
});

afterAll(() => {
  vi.useRealTimers();
});

describe('DESIGN_DIRECTION.md §7 before/after table', () => {
  it('"10/14/2026, 10:00:00 AM – 12:00:00 PM" -> "Wed 14 Oct · 10:00–12:00"', () => {
    const start = new Date(2026, 9, 14, 10, 0);
    const end = new Date(2026, 9, 14, 12, 0);
    expect(`${formatDay(start)} · ${formatTimeRange(start, end)}`).toBe('Wed 14 Oct · 10:00–12:00');
  });

  it('"2026-10-15 from 10:00–12:00" -> "Thu 15 Oct, 10:00–12:00"', () => {
    const start = new Date(2026, 9, 15, 10, 0);
    const end = new Date(2026, 9, 15, 12, 0);
    expect(`${formatDay(start)}, ${formatTimeRange(start, end)}`).toBe('Thu 15 Oct, 10:00–12:00');
  });

  it('"Booked 8/26/2026, 9:50:02 AM" -> "Requested 26 Aug"', () => {
    const createdAt = new Date(2026, 7, 26, 9, 50, 2);
    expect(`Requested ${formatRelative(createdAt)}`).toBe('Requested 26 Aug');
  });

  it('"September 27 – October 03" -> "27 Sep – 3 Oct"', () => {
    const start = new Date(2026, 8, 27);
    const end = new Date(2026, 9, 3);
    expect(formatDateRange(start, end)).toBe('27 Sep – 3 Oct');
  });

  it('"07 Oct 2026 00:00" -> day-first, no zero-pad, correct local time (not UTC midnight)', () => {
    // The doc's own example date (7 Oct 2026) is a Wednesday, not the "Fri" it
    // shows — an inconsistency in the illustrative table, not a module bug.
    // What matters is the two real violations this example calls out: no
    // zero-padded day, and the actual local time instead of a UTC-midnight
    // artifact — both of which this composition fixes.
    const d = new Date(2026, 9, 7, 19, 0);
    expect(`${formatDay(d)}, ${formatTime(d)}`).toBe('Wed 7 Oct, 19:00');
  });
});

describe('formatDay', () => {
  it('omits the year in the current year', () => {
    expect(formatDay(new Date(2026, 9, 14))).toBe('Wed 14 Oct');
  });

  it('includes the year when not the current year', () => {
    expect(formatDay(new Date(2027, 9, 14))).toBe('Thu 14 Oct 2027');
  });

  it('never zero-pads the day number', () => {
    expect(formatDay(new Date(2026, 9, 3))).toBe('Sat 3 Oct');
  });
});

describe('formatDayShort', () => {
  it('has no weekday', () => {
    expect(formatDayShort(new Date(2026, 7, 26))).toBe('26 Aug');
  });
});

describe('formatDayLong', () => {
  it('spells out weekday, day, month, and year', () => {
    expect(formatDayLong(new Date(2026, 9, 14))).toBe('Wednesday 14 October 2026');
  });
});

describe('formatTime', () => {
  it('is 24-hour with no seconds', () => {
    expect(formatTime(new Date(2026, 9, 14, 19, 5))).toBe('19:05');
  });
});

describe('formatSlot', () => {
  it('includes day, time range, and whole-hour duration', () => {
    const start = new Date(2026, 9, 14, 10, 0);
    const end = new Date(2026, 9, 14, 12, 0);
    expect(formatSlot(start, end)).toBe('Wed 14 Oct · 10:00–12:00 · 2 hours');
  });

  it('uses minutes for sub-hour durations', () => {
    const start = new Date(2026, 9, 14, 10, 0);
    const end = new Date(2026, 9, 14, 10, 45);
    expect(formatSlot(start, end)).toBe('Wed 14 Oct · 10:00–10:45 · 45 min');
  });

  it('singularizes a one-hour duration', () => {
    const start = new Date(2026, 9, 14, 10, 0);
    const end = new Date(2026, 9, 14, 11, 0);
    expect(formatSlot(start, end)).toBe('Wed 14 Oct · 10:00–11:00 · 1 hour');
  });
});

describe('formatRelative', () => {
  it('says "today" for the current day', () => {
    expect(formatRelative(new Date(2026, 9, 1, 8, 0))).toBe('today');
  });

  it('says "yesterday" for one day ago', () => {
    expect(formatRelative(new Date(2026, 8, 30))).toBe('yesterday');
  });

  it('counts days for up to a week ago', () => {
    expect(formatRelative(new Date(2026, 8, 27))).toBe('4 days ago');
  });

  it('falls back to an absolute short date beyond a week', () => {
    expect(formatRelative(new Date(2026, 8, 20))).toBe('20 Sep');
  });
});
