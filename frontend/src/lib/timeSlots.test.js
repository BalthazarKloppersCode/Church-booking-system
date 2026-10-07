import { describe, expect, it } from 'vitest';
import { END_SLOTS, START_SLOTS, durationLabel, fromMinutes, slotsWithValue, toMinutes } from './timeSlots';

describe('slot lists', () => {
  it('start slots run 00:00–23:00 and end slots 00:30–23:30 on the half hour', () => {
    expect(START_SLOTS[0]).toBe('00:00');
    expect(START_SLOTS.at(-1)).toBe('23:00');
    expect(START_SLOTS).toHaveLength(47);
    expect(END_SLOTS[0]).toBe('00:30');
    expect(END_SLOTS.at(-1)).toBe('23:30');
  });
});

describe('slotsWithValue', () => {
  it('leaves the list alone when the value is on the grid', () => {
    expect(slotsWithValue(START_SLOTS, '10:30')).toBe(START_SLOTS);
  });

  it('adds and sorts in an off-grid value so it can still be shown', () => {
    const slots = slotsWithValue(START_SLOTS, '10:15');
    expect(slots).toContain('10:15');
    expect(slots.indexOf('10:15')).toBe(slots.indexOf('10:00') + 1);
  });
});

describe('time maths', () => {
  it('round-trips and clamps at the end of the day', () => {
    expect(toMinutes('10:30')).toBe(630);
    expect(fromMinutes(630)).toBe('10:30');
    expect(fromMinutes(24 * 60 + 90)).toBe('23:59');
  });
});

describe('durationLabel', () => {
  it.each([
    [30, '30 min'],
    [60, '1 hour'],
    [90, '1.5 hours'],
    [120, '2 hours'],
    [210, '3.5 hours'],
  ])('%i minutes -> %s', (minutes, label) => {
    expect(durationLabel(minutes)).toBe(label);
  });
});
