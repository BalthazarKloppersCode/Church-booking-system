// Helpers for the "Repeats / Until" fields of the new-booking sheet. Dates are
// 'YYYY-MM-DD' strings (what the date picker holds), read as plain calendar dates.

function pad(n) {
  return String(n).padStart(2, '0');
}

export function toDateValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseDate(value) {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d);
}

// Same day-of-month `n` months on, clamped to the month's last day (31 Jan + 1 month = 28/29 Feb).
export function addMonths(date, n) {
  const target = new Date(date.getFullYear(), date.getMonth() + n, 1);
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  return new Date(target.getFullYear(), target.getMonth(), Math.min(date.getDate(), lastDay));
}

// What "Until" starts at when a repeat is chosen: three months after the first booking.
export function defaultUntil(startValue) {
  return toDateValue(addMonths(parseDate(startValue), 3));
}

// Monday-first, matching the server (Monday = 0 ... Sunday = 6).
export const WEEKDAYS = [
  { value: 0, short: 'Mon', long: 'Monday' },
  { value: 1, short: 'Tue', long: 'Tuesday' },
  { value: 2, short: 'Wed', long: 'Wednesday' },
  { value: 3, short: 'Thu', long: 'Thursday' },
  { value: 4, short: 'Fri', long: 'Friday' },
  { value: 5, short: 'Sat', long: 'Saturday' },
  { value: 6, short: 'Sun', long: 'Sunday' },
];

// Which weekday a 'YYYY-MM-DD' date falls on, Monday = 0.
export function weekdayOf(dateValue) {
  return (parseDate(dateValue).getDay() + 6) % 7;
}

// "Monday", "Monday and Friday", "Monday, Tuesday and Friday"
export function describeWeekdays(days) {
  const names = [...days].sort((a, b) => a - b).map((d) => WEEKDAYS[d].long);
  return names.length <= 1 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// A weekly / every-2-weeks repeat on chosen days: the first chosen day on or after the start, then
// every chosen day of every 1st (or 2nd) week, up to and including "until". Mirrors the server.
function countOnWeekdays(start, until, frequency, weekdays) {
  const step = frequency === 'weekly' ? 1 : 2;
  const monday = new Date(start.getFullYear(), start.getMonth(), start.getDate() - weekdayOf(toDateValue(start)));
  let count = 0;
  for (let week = 0; count <= 104; week++) {
    const weekStart = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + week * step * 7);
    if (weekStart > until) break;
    for (const d of weekdays) {
      const day = new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + d);
      if (day >= start && day <= until) count++;
    }
  }
  return count;
}

// How many bookings a repeat creates, counting the first — mirrors the server's rule
// (a date is included while it is on or before "until").
export function countOccurrences(startValue, untilValue, frequency, weekdays) {
  const start = parseDate(startValue);
  const until = parseDate(untilValue);
  if (weekdays?.length && frequency !== 'monthly') return countOnWeekdays(start, until, frequency, weekdays);
  let count = 1;
  for (let i = 1; count <= 104; i++) {
    const next =
      frequency === 'monthly'
        ? addMonths(start, i)
        : new Date(start.getFullYear(), start.getMonth(), start.getDate() + i * (frequency === 'weekly' ? 7 : 14));
    if (next > until) break;
    count++;
  }
  return count;
}
