import { useEffect, useMemo, useState } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import '../lib/calendarTheme.css';
import { api } from '../lib/api';
import { CALENDAR_FORMATS } from '../lib/calendarFormats';

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date) => startOfWeek(date, { weekStartsOn: 1 }),
  getDay,
  locales: { 'en-US': enUS },
});

const STATUS_COLOR = {
  approved: 'var(--ok)',
  pending: 'var(--wait)',
  external: 'var(--ink-3)',
};

const LEGEND = [
  { status: 'approved', label: 'Confirmed' },
  { status: 'pending', label: 'Awaiting the office' },
  { status: 'external', label: 'Already on the church calendar' },
];

// Shown by default; "Show full day" expands to the full 00:00–24:00 range.
const COLLAPSED_MIN = new Date(1970, 0, 1, 6, 0, 0);
const COLLAPSED_MAX = new Date(1970, 0, 1, 21, 59, 59);
const FULL_MIN = new Date(1970, 0, 1, 0, 0, 0);
const FULL_MAX = new Date(1970, 0, 1, 23, 59, 59);

function pad(n) {
  return String(n).padStart(2, '0');
}

function fmtTime(d) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Bookers only ever see room + timeslot here — never who booked it or why.
// Fetched separately from the admin calendar's data source (a lean,
// privacy-safe endpoint) rather than reusing the full booking record.
export default function BookerCalendar({ onPick, onClose }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fullDay, setFullDay] = useState(false);

  useEffect(() => {
    const now = new Date();
    const start_after = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7).toISOString();
    const start_before = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 90).toISOString();
    Promise.all([
      api.listBookingsCalendar({ start_after, start_before }),
      // Falls back to [] on its own if the church Google Calendar isn't
      // connected — never blocks the booking calendar from loading.
      api.listExternalCalendarEvents({ start_after, start_before }).catch(() => []),
    ])
      .then(([entries, externalEvents]) => {
        const bookingEvents = entries.map((e, i) => {
          const start = new Date(e.start_time);
          const end = new Date(e.end_time);
          return {
            id: `booking-${i}`,
            title: `${e.room_name} (${fmtTime(start)}–${fmtTime(end)})`,
            start,
            end,
            status: e.status,
          };
        });
        const churchEvents = externalEvents.map((e, i) => {
          const start = new Date(e.start_time);
          const end = new Date(e.end_time);
          return {
            id: `external-${i}`,
            title: `${e.title} (church calendar)`,
            start,
            end,
            allDay: Boolean(e.all_day),
            status: 'external',
          };
        });
        setEvents([...bookingEvents, ...churchEvents]);
      })
      .finally(() => setLoading(false));
  }, []);

  const eventStyleGetter = useMemo(
    () => (event) => ({
      style: {
        backgroundColor: STATUS_COLOR[event.status] || '#5B6259',
        borderRadius: 6,
        border: 'none',
        fontSize: 12,
      },
    }),
    []
  );

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(18,41,77,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ width: '100%', maxWidth: 920, maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>Browse the calendar</h3>
          <button type="button" className="btn btn-ghost" style={{ padding: '2px 8px' }} onClick={onClose}>✕</button>
        </div>
        <p style={{ fontSize: 13, color: 'var(--ink-2)', marginBottom: 10 }}>
          Blank hours are free. Tap an hour to pick that date and time — it'll take you back to the
          booking form with it filled in.
        </p>
        <button type="button" className="cal-collapse-toggle" onClick={() => setFullDay((f) => !f)}>
          {fullDay ? '▴ Show less' : '▾ Show full day · 00:00–06:00 and 22:00–24:00 hidden'}
        </button>
        {loading ? (
          <p>Loading calendar…</p>
        ) : (
          <Calendar
            localizer={localizer}
            events={events}
            startAccessor="start"
            endAccessor="end"
            defaultView="week"
            views={['week', 'day']}
            step={60}
            timeslots={1}
            min={fullDay ? FULL_MIN : COLLAPSED_MIN}
            max={fullDay ? FULL_MAX : COLLAPSED_MAX}
            formats={CALENDAR_FORMATS}
            style={{ flex: 1, minHeight: 0 }}
            eventPropGetter={eventStyleGetter}
            selectable
            onSelectSlot={(slotInfo) => onPick(slotInfo.start, slotInfo.end)}
            onSelectEvent={() => {}}
          />
        )}
        <div className="cal-legend">
          {LEGEND.map((l) => (
            <span key={l.status}>
              <span className="dot" style={{ background: STATUS_COLOR[l.status] }} />
              {l.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
