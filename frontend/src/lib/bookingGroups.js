// An event booked into several rooms is stored as one booking per room (so each
// room's availability stays simple), tied together by a shared group_id. People
// think of it as ONE booking, so every list and calendar folds the rooms back
// into a single entry: the first room's booking stands in for the event, with
//   rooms     — [{ id, name }] for every room
//   ids       — every underlying booking id (for deleting/editing them together)
//   room_name — "Main Hall, Foyer" so existing displays just work
export function groupBookings(bookings) {
  const merged = [];
  const byGroup = new Map();
  for (const b of bookings) {
    const room = { id: b.room_id, name: b.room_name };
    const existing = b.group_id ? byGroup.get(b.group_id) : null;
    if (existing) {
      existing.rooms.push(room);
      existing.ids.push(b.id);
      existing.room_name = existing.rooms.map((r) => r.name).join(', ');
      continue;
    }
    const entry = { ...b, rooms: [room], ids: [b.id] };
    if (b.group_id) byGroup.set(b.group_id, entry);
    merged.push(entry);
  }
  return merged;
}

// The same fold for the booker-facing calendar, whose entries carry no ids —
// just room_name, times, status and the group_id.
export function groupCalendarEntries(entries) {
  const merged = [];
  const byGroup = new Map();
  for (const e of entries) {
    const existing = e.group_id ? byGroup.get(e.group_id) : null;
    if (existing) {
      existing.rooms.push(e.room_name);
      existing.room_name = existing.rooms.join(', ');
      continue;
    }
    const entry = { ...e, rooms: [e.room_name] };
    if (e.group_id) byGroup.set(e.group_id, entry);
    merged.push(entry);
  }
  return merged;
}
