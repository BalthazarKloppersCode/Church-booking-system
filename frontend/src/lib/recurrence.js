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

// How many bookings a repeat creates, counting the first — mirrors the server's rule
// (a date is included while it is on or before "until").
export function countOccurrences(startValue, untilValue, frequency) {
  const start = parseDate(startValue);
  const until = parseDate(untilValue);
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
