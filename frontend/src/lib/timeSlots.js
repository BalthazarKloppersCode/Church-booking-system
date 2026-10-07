// Rooms book on the half hour (DESIGN_DIRECTION.md §6 Fields), so times are
// picked from a list of slots rather than typed into a free clock input.

export const SLOT_MINUTES = 30;
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

export const ALL_SLOTS = slotRange('00:00', '23:30');
// A booking needs room for at least one slot on the same day.
export const START_SLOTS = slotRange('00:00', '23:00');
export const END_SLOTS = slotRange('00:30', '23:30');

/** The slots to render for `value`: the base list, plus `value` itself if it's off-grid (e.g. an existing 10:15 booking, or an end clamped to 23:59). */
export function slotsWithValue(base, value) {
  if (!value || base.includes(value)) return base;
  return [...base, value].sort((a, b) => toMinutes(a) - toMinutes(b));
}

/** 30 -> "30 min", 60 -> "1 hour", 90 -> "1.5 hours", 120 -> "2 hours". */
export function durationLabel(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours} hour${hours === 1 ? '' : 's'}`;
}
