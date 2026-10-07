import dfFormat from 'date-fns/format';
import { formatDateRange, formatDay, formatTime, formatTimeRange } from './formatDate';

// react-big-calendar's own defaults render 12-hour AM/PM times and
// zero-padded dates — both violate DESIGN_DIRECTION.md §7. These override
// every format callback the library actually uses in week/day/month views,
// reusing formatDate.js where the shape matches so the calendar reads the
// same way the rest of the app does.
export const CALENDAR_FORMATS = {
  timeGutterFormat: (date) => dfFormat(date, 'HH:mm'),
  dayFormat: (date) => dfFormat(date, 'EEE d'), // week-view day column header, e.g. "Mon 28" — no month, it's already in the range label above
  dayHeaderFormat: (date) => formatDay(date), // day-view's single header, e.g. "Wed 14 Oct"
  dayRangeHeaderFormat: ({ start, end }) => formatDateRange(start, end), // week-view toolbar label, e.g. "28 Sep – 4 Oct"
  monthHeaderFormat: (date) => dfFormat(date, 'MMMM yyyy'),
  weekdayFormat: (date) => dfFormat(date, 'EEE'),
  // The time label inside an event block, the label while dragging a selection,
  // and the agenda view — all default to 12-hour AM/PM otherwise.
  eventTimeRangeFormat: ({ start, end }) => formatTimeRange(start, end),
  eventTimeRangeStartFormat: ({ start }) => `${formatTime(start)} –`,
  eventTimeRangeEndFormat: ({ end }) => `– ${formatTime(end)}`,
  selectRangeFormat: ({ start, end }) => formatTimeRange(start, end),
  agendaTimeFormat: (date) => formatTime(date),
  agendaTimeRangeFormat: ({ start, end }) => formatTimeRange(start, end),
};
