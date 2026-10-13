import { describe, expect, it } from 'vitest';
import { groupBookings, groupCalendarEntries } from './bookingGroups';

const base = { start_time: '2026-10-14T13:00:00+00:00', end_time: '2026-10-14T14:30:00+00:00', status: 'approved' };

describe('groupBookings', () => {
  const bookings = [
    { id: 'a', room_id: 'r1', room_name: 'Main Hall', group_id: 'g1', ...base },
    { id: 'b', room_id: 'r2', room_name: 'Foyer', group_id: 'g1', ...base },
    { id: 'c', room_id: 'r3', room_name: 'Kitchen', group_id: null, ...base },
    { id: 'd', room_id: 'r1', room_name: 'Main Hall', group_id: 'g2', ...base },
  ];

  it('folds the rooms of one event into a single entry', () => {
    const merged = groupBookings(bookings);
    expect(merged).toHaveLength(3);
    const event = merged[0];
    expect(event.room_name).toBe('Main Hall, Foyer');
    expect(event.rooms).toEqual([
      { id: 'r1', name: 'Main Hall' },
      { id: 'r2', name: 'Foyer' },
    ]);
    expect(event.ids).toEqual(['a', 'b']);
    expect(event.id).toBe('a');
  });

  it('leaves ungrouped and single-room entries alone', () => {
    const merged = groupBookings(bookings);
    expect(merged[1].room_name).toBe('Kitchen');
    expect(merged[1].ids).toEqual(['c']);
    expect(merged[2].rooms).toHaveLength(1);
  });

  it("keeps different dates of a repeating event apart (each date has its own group)", () => {
    expect(groupBookings(bookings).map((b) => b.group_id)).toEqual(['g1', null, 'g2']);
  });

  it('does not change what it is given', () => {
    const copy = JSON.parse(JSON.stringify(bookings));
    groupBookings(bookings);
    expect(bookings).toEqual(copy);
  });
});

describe('groupCalendarEntries', () => {
  it('joins the room names of one event', () => {
    const entries = [
      { room_name: 'Main Hall', group_id: 'g1', ...base },
      { room_name: 'Foyer', group_id: 'g1', ...base },
      { room_name: 'Kitchen', group_id: null, ...base },
    ];
    const merged = groupCalendarEntries(entries);
    expect(merged.map((e) => e.room_name)).toEqual(['Main Hall, Foyer', 'Kitchen']);
    expect(merged[0].rooms).toEqual(['Main Hall', 'Foyer']);
    expect(entries[0].room_name).toBe('Main Hall');
  });
});
