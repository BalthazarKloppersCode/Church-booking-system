import { describe, expect, it } from 'vitest';
import { eventName, eventTitle } from './eventLabel';

const base = { purpose: 'Bible study', room_name: 'Main Hall', congregation: 'Youth Group', headcount: 20 };

describe('eventName', () => {
  it('uses the purpose picked from the list', () => {
    expect(eventName(base)).toBe('Bible study');
  });

  it('prefers what was typed for Other', () => {
    expect(eventName({ ...base, purpose: 'Other', purpose_other: ' Wedding rehearsal ' })).toBe('Wedding rehearsal');
  });

  it('ignores a blank detail and never comes back empty', () => {
    expect(eventName({ ...base, purpose_other: '   ' })).toBe('Bible study');
    expect(eventName({ ...base, purpose: '' })).toBe('Booking');
  });
});

describe('eventTitle', () => {
  it('reads event, room, congregation', () => {
    expect(eventTitle(base)).toBe('Bible study — Main Hall — Youth Group (20)');
    expect(eventTitle({ ...base, room_name: 'Main Hall, Foyer' })).toBe('Bible study — Main Hall, Foyer — Youth Group (20)');
  });
});
