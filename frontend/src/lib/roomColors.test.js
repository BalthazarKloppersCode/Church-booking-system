import { describe, expect, it } from 'vitest';
import { MULTI_ROOM_COLOR, NO_ROOM_COLOR, buildRoomColors, colorForRoomNames, colorForRooms, eventStyle } from './roomColors';

const rooms = ['a1', 'b2', 'c3', 'd4', 'e5', 'f6', 'g7', 'h8', 'i9', 'j10', 'k11', 'l12'].map((id) => ({ id, name: `Room ${id}` }));

describe('buildRoomColors', () => {
  it('gives every room its own colour', () => {
    const { byId } = buildRoomColors(rooms);
    expect(new Set(Object.values(byId)).size).toBe(rooms.length);
  });

  it('does not change a room colour when another room is added or the list is reordered', () => {
    const before = buildRoomColors(rooms).byId;
    const after = buildRoomColors([...rooms, { id: 'm13', name: 'New' }].reverse()).byId;
    for (const id of Object.keys(before)) expect(after[id]).toBe(before[id]);
  });

  it('never picks the colours kept for several rooms or no room', () => {
    const colors = Object.values(buildRoomColors(rooms).byId);
    expect(colors).not.toContain(MULTI_ROOM_COLOR);
    expect(colors).not.toContain(NO_ROOM_COLOR);
  });

  it('stays out of the amber band that means "awaiting approval"', () => {
    const many = Array.from({ length: 60 }, (_, i) => ({ id: `r${String(i).padStart(2, '0')}`, name: `R${i}` }));
    for (const c of Object.values(buildRoomColors(many).byId)) {
      const hue = Number(/hsl\((\d+)/.exec(c)[1]);
      expect(hue < 28 || hue > 62).toBe(true);
    }
  });
});

describe('colorForRooms', () => {
  const colors = buildRoomColors(rooms);

  it('uses the room colour for one room, however many times it is listed', () => {
    expect(colorForRooms(['a1'], colors)).toBe(colors.byId.a1);
    expect(colorForRooms(['a1', 'a1'], colors)).toBe(colors.byId.a1);
  });

  it('uses one shared colour for several rooms', () => {
    expect(colorForRooms(['a1', 'b2'], colors)).toBe(MULTI_ROOM_COLOR);
    expect(colorForRooms(['b2', 'c3', 'd4'], colors)).toBe(MULTI_ROOM_COLOR);
  });

  it('is grey when there is no (known) room', () => {
    expect(colorForRooms([], colors)).toBe(NO_ROOM_COLOR);
    expect(colorForRooms(undefined, colors)).toBe(NO_ROOM_COLOR);
    expect(colorForRooms(['gone'], colors)).toBe(NO_ROOM_COLOR);
  });

  it('works from room names for the booker calendar', () => {
    expect(colorForRoomNames(['Room a1'], colors)).toBe(colors.byId.a1);
    expect(colorForRoomNames(['Room a1', 'Room b2'], colors)).toBe(MULTI_ROOM_COLOR);
    expect(colorForRoomNames(['Nope'], colors)).toBe(NO_ROOM_COLOR);
  });
});

describe('eventStyle', () => {
  it('fills a confirmed event with the room colour', () => {
    expect(eventStyle('red', 'approved')).toMatchObject({ backgroundColor: 'red', color: '#fff' });
  });

  it('shows an event awaiting approval in its own cream style with the room colour as a bar', () => {
    const s = eventStyle('red', 'pending');
    expect(s.backgroundColor).toBe('var(--wait-bg)');
    expect(s.borderLeft).toContain('red');
  });
});
