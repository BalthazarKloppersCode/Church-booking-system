import { differenceInCalendarDays, differenceInMinutes, format, isSameYear } from 'date-fns';

// Single source of truth for every date/time string shown to a user — see
// DESIGN_DIRECTION.md §7. No component should call toLocaleString(),
// toLocaleDateString(), toLocaleTimeString(), or build a date string by hand.

const RELATIVE_FALLBACK_DAYS = 7; // beyond this, show an absolute short date instead of "N days ago"

function toDate(d) {
  return d instanceof Date ? d : new Date(d);
}

function withYear(date, shortPattern) {
  return format(date, isSameYear(date, new Date()) ? shortPattern : `${shortPattern} yyyy`);
}

/** "Wed 14 Oct" — adds the year only when it isn't the current year. */
export function formatDay(d) {
  return withYear(toDate(d), 'EEE d MMM');
}

/** "26 Aug" — same as formatDay but without the weekday, for secondary/meta text. */
export function formatDayShort(d) {
  return withYear(toDate(d), 'd MMM');
}

/** "Wednesday 14 October 2026" — full form, e.g. for a tooltip's exact date. */
export function formatDayLong(d) {
  return format(toDate(d), 'EEEE d MMMM yyyy');
}

/** "Wed 14 October 2026" — a date field's closed state; always shows the year. */
export function formatDayFull(d) {
  return format(toDate(d), 'EEE d MMMM yyyy');
}

/** "10:00" — 24-hour, no seconds. */
export function formatTime(d) {
  return format(toDate(d), 'HH:mm');
}

/** "10:00–12:00" — en dash, no spaces. */
export function formatTimeRange(a, b) {
  return `${formatTime(a)}–${formatTime(b)}`;
}

function formatDuration(a, b) {
  const minutes = differenceInMinutes(toDate(b), toDate(a));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours} hour${hours === 1 ? '' : 's'}`;
}

/** "Wed 14 Oct · 10:00–12:00 · 2 hours" — the standard booking-row summary. */
export function formatSlot(a, b) {
  return `${formatDay(a)} · ${formatTimeRange(a, b)} · ${formatDuration(a, b)}`;
}

/** "27 Sep – 3 Oct" — a span across two dates, e.g. a week bucket in a chart. */
export function formatDateRange(a, b) {
  const start = toDate(a);
  const end = toDate(b);
  const sameYear = isSameYear(start, new Date()) && isSameYear(end, new Date());
  const pattern = sameYear ? 'd MMM' : 'd MMM yyyy';
  return `${format(start, pattern)} – ${format(end, pattern)}`;
}

/**
 * "today" / "yesterday" / "3 days ago", falling back to an absolute short
 * date ("26 Aug") past RELATIVE_FALLBACK_DAYS — an unreadable "47 days ago"
 * is worse than just saying the date. Callers should put formatDayLong(d)
 * in a title attribute alongside this so the exact date is a hover away.
 */
export function formatRelative(d) {
  const date = toDate(d);
  const days = differenceInCalendarDays(new Date(), date);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < RELATIVE_FALLBACK_DAYS) return `${days} days ago`;
  return formatDayShort(date);
}
