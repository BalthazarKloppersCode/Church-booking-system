import { describe, expect, it } from 'vitest';
import { describeCreated } from './createdSummary';

const at = (iso, room = 'Main Hall') => ({ start_time: iso, room_name: room });

describe('describeCreated', () => {
  it('says how many bookings a repeat made, and the span', () => {
    const text = describeCreated({ bookings: [at('2026-10-14T13:00:00Z'), at('2026-10-21T13:00:00Z'), at('2026-10-28T13:00:00Z')] });
    expect(text).toMatch(/^3 bookings created: .+ to .+\.$/);
  });

  it('counts dates, not rooms, for a multi-room repeat', () => {
    const text = describeCreated({
      bookings: [at('2026-10-14T13:00:00Z'), at('2026-10-14T13:00:00Z', 'Foyer'), at('2026-10-21T13:00:00Z'), at('2026-10-21T13:00:00Z', 'Foyer')],
    });
    expect(text).toMatch(/^2 bookings created in 2 rooms:/);
  });

  it('is plain for a single booking', () => {
    expect(describeCreated({ bookings: [at('2026-10-14T13:00:00Z')] })).toMatch(/^Booking created for .+\.$/);
    expect(describeCreated({})).toBe('Booking created.');
  });
});
