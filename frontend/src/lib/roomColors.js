// One colour per room on the calendars, so you can tell at a glance which room is taken.
//  - A booking or church-calendar event in ONE room takes that room's colour.
//  - Several rooms at once share a single "several rooms" colour (the card lists the rooms).
//  - An event with no room set yet is grey.
//  - Anything still waiting for approval keeps a look of its own (cream, dashed) with the room's
//    colour as a bar down the left side, so it is clearly "not confirmed yet" and still shows the room.
// Confirmed bookings and church-calendar events are plain room colours with no extra marker.

export const MULTI_ROOM_COLOR = '#2B3140';
export const NO_ROOM_COLOR = '#8C94A0';

// Colours are handed out in the order rooms were created (ids are creation-ordered), so adding or
// renaming a room never changes another room's colour. Hues step by the golden angle so rooms
// listed next to each other look different, and the amber band is skipped (that's "awaiting").
function colorAt(index) {
  let hue = (index * 137.508 + 215) % 360;
  if (hue >= 26 && hue <= 66) hue += 42;
  const saturation = [58, 66, 50][index % 3];
  const lightness = [34, 40][index % 2];
  return `hsl(${Math.round(hue % 360)} ${saturation}% ${lightness}%)`;
}

// rooms: [{ id, name }]  ->  { byId, byName }
export function buildRoomColors(rooms) {
  const ordered = [...rooms].sort((a, b) => String(a.id).localeCompare(String(b.id)));
  const byId = {};
  const byName = {};
  ordered.forEach((room, i) => {
    byId[room.id] = colorAt(i);
    byName[room.name] = byId[room.id];
  });
  return { byId, byName };
}

// The colour for an event in these rooms (ids). Unknown rooms count as "no room".
export function colorForRooms(roomIds, colors) {
  const known = [...new Set(roomIds || [])].filter((id) => colors.byId[id]);
  if (known.length === 0) return NO_ROOM_COLOR;
  return known.length === 1 ? colors.byId[known[0]] : MULTI_ROOM_COLOR;
}

// Same, for the booker calendar, whose entries carry room names rather than ids.
export function colorForRoomNames(roomNames, colors) {
  const known = [...new Set(roomNames || [])].filter((name) => colors.byName[name]);
  if (known.length === 0) return NO_ROOM_COLOR;
  return known.length === 1 ? colors.byName[known[0]] : MULTI_ROOM_COLOR;
}

// The react-big-calendar `style` for an event of this colour.
export function eventStyle(color, status) {
  if (status === 'pending') {
    return {
      backgroundColor: 'var(--wait-bg)',
      color: 'var(--wait)',
      border: '1px dashed var(--wait)',
      borderLeft: `6px solid ${color}`,
      borderRadius: 6,
    };
  }
  return { backgroundColor: color, color: '#fff', border: 'none', borderRadius: 6 };
}
