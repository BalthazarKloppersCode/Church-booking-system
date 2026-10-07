// Rooms book on the half hour (DESIGN_DIRECTION.md §6 Fields), so times are
// picked from a list of slots rather than typed into a free clock input.

export const SLOT_MINUTES = 30;
export const DEFAULT_FIRST = '06:00';
export const DEFAULT_LAST = '21:30'; // matches the calendar's collapsed 06:00–22:00 window
export const DAY_LAST_MINUTE = 23 * 60 + 59;

export function toMinutes(time) {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

export function fromMinutes(total) {
  const clamped = Math.max(0, Math.min(total, DAY_LAST_MINUTE));
  return `${String(Math.floor(clamped / 60)).padStart(2, '0')}:${String(clamped % 60).padStart(2, '0')}`;
}

export function slotRange(first, last) {
  const slots = [];
  for (let m = toMinutes(first); m <= toMinutes(last); m += SLOT_MINUTES) slots.push(fromMinutes(m));
  return slots;
}

export const DEFAULT_SLOTS = slotRange(DEFAULT_FIRST, DEFAULT_LAST);
export const ALL_SLOTS = slotRange('00:00', '23:30');

export function isDefaultSlot(time) {
  return DEFAULT_SLOTS.includes(time);
}

/** The slots to render for `value`: the base list, plus `value` itself if it's off-grid (e.g. an existing 10:15 booking being edited). */
export function slotsWithValue(base, value) {
  if (!value || base.includes(value)) return base;
  return [...base, value].sort((a, b) => toMinutes(a) - toMinutes(b));
}
