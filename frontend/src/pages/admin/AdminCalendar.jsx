import { useEffect, useMemo, useState } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import '../../lib/calendarTheme.css';
import { api } from '../../lib/api';
import { formatDay, formatTimeRange } from '../../lib/formatDate';
import { CALENDAR_FORMATS } from '../../lib/calendarFormats';
import Select from '../../components/fields/Select';
import NewBookingSheet from '../../components/admin/NewBookingSheet';
import { bookingBadge } from '../../lib/bookingStatus';

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

function Modal({ title, onClose, children }) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(18,41,77,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 20,
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ width: 480, maxWidth: '100%', maxHeight: '85vh', overflowY: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, margin: 0 }}>{title}</h3>
          <button type="button" className="btn btn-ghost" style={{ padding: '2px 8px' }} onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function AdminCalendar() {
  const [rooms, setRooms] = useState([]);
  const [roomFilter, setRoomFilter] = useState('');
  const [events, setEvents] = useState([]);

  const [newBookingSlot, setNewBookingSlot] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [view, setView] = useState('week');
  const [fullDay, setFullDay] = useState(false);

  useEffect(() => {
    api.listRooms().then(setRooms);
  }, []);

  useEffect(() => {
    Promise.all([
      api.listBookings(roomFilter ? { room_id: roomFilter } : {}),
      // Only shown when no room filter is set — external church-calendar
      // events aren't tied to a specific bookable room.
      roomFilter ? Promise.resolve([]) : api.listExternalCalendarEvents().catch(() => []),
    ]).then(([bookings, externalEvents]) => {
      const filtered = bookings.filter((b) => b.status === 'approved' || b.status === 'pending');
      const bookingEvents = filtered.map((b) => ({
        id: b.id,
        title: `${b.room_name} — ${b.congregation} (${b.headcount})`,
        start: new Date(b.start_time),
        end: new Date(b.end_time),
        status: b.status,
        booking: b,
      }));
      const churchEvents = externalEvents.map((e, i) => ({
        id: `external-${i}`,
        title: `${e.title} (church calendar)`,
        start: new Date(e.start_time),
        end: new Date(e.end_time),
        allDay: Boolean(e.all_day),
        status: 'external',
        booking: null,
      }));
      setEvents([...bookingEvents, ...churchEvents]);
    });
  }, [roomFilter, refreshKey]);

  const eventStyleGetter = useMemo(
    () => (event) => ({
      style: {
        backgroundColor: STATUS_COLOR[event.status] || 'var(--ink-3)',
        borderRadius: 6,
        border: 'none',
      },
    }),
    []
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1>Calendar</h1>
        <Select
          size="admin"
          aria-label="Filter by room"
          value={roomFilter}
          onChange={(e) => setRoomFilter(e.target.value)}
          style={{ width: 220 }}
        >
          <option value="">All rooms</option>
          {rooms.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </Select>
      </div>
      <p style={{ fontSize: 13, color: 'var(--ink-2)', marginBottom: 10 }}>
        Click and drag on an empty slot to add a booking directly — admin-created bookings are
        confirmed instantly and can repeat weekly, every 2 weeks, or monthly.
      </p>
      {(view === 'week' || view === 'day') && (
        <button type="button" className="cal-collapse-toggle" onClick={() => setFullDay((f) => !f)}>
          {fullDay ? '▴ Show less' : '▾ Show full day · 00:00–06:00 and 22:00–24:00 hidden'}
        </button>
      )}
      <div className="card" style={{ padding: 16 }}>
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          view={view}
          onView={setView}
          views={['month', 'week', 'day']}
          min={fullDay ? FULL_MIN : COLLAPSED_MIN}
          max={fullDay ? FULL_MAX : COLLAPSED_MAX}
          formats={CALENDAR_FORMATS}
          style={{ height: 650 }}
          eventPropGetter={eventStyleGetter}
          selectable
          onSelectSlot={(slotInfo) => setNewBookingSlot({ start: slotInfo.start, end: slotInfo.end })}
          onSelectEvent={(event) => {
            if (event.booking) setSelectedEvent(event.booking);
          }}
        />
      </div>
      <div className="cal-legend">
        {LEGEND.filter((l) => l.status !== 'external' || !roomFilter).map((l) => (
          <span key={l.status}>
            <span className="dot" style={{ background: STATUS_COLOR[l.status] }} />
            {l.label}
          </span>
        ))}
      </div>

      {newBookingSlot && (
        <NewBookingSheet
          slot={newBookingSlot}
          defaultRoomId={roomFilter}
          onClose={() => setNewBookingSlot(null)}
          onCreated={() => {
            setNewBookingSlot(null);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}

      {selectedEvent && (
        <EventDetailModal
          booking={selectedEvent}
          onClose={() => setSelectedEvent(null)}
          onChanged={() => {
            setSelectedEvent(null);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}

function EventDetailModal({ booking, onClose, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function cancelOne() {
    if (!confirm('Cancel this booking?')) return;
    setBusy(true);
    setError('');
    try {
      await api.adminCancelBooking(booking.id);
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  async function cancelSeries() {
    if (!confirm('Cancel every booking in this repeating series? This cannot be undone.')) return;
    setBusy(true);
    setError('');
    try {
      await api.adminCancelSeries(booking.series_id);
      onChanged();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <Modal title={booking.room_name} onClose={onClose}>
      {error && <p style={{ color: 'var(--no)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
      <p style={{ fontSize: 14, marginBottom: 4 }}>
        <strong>{booking.congregation}</strong> · {booking.headcount} people
      </p>
      <p style={{ fontSize: 13, color: 'var(--ink-2)', marginBottom: 4 }}>
        {formatDay(booking.start_time)} · {formatTimeRange(booking.start_time, booking.end_time)}
      </p>
      <p style={{ fontSize: 13, marginBottom: 4 }}>{booking.purpose}{booking.purpose_other ? `: ${booking.purpose_other}` : ''}</p>
      <p style={{ fontSize: 13, marginBottom: 16 }}>
        Requested by {booking.requester_name} · {booking.email} · {booking.phone}
      </p>
      <span className={`badge badge-${bookingBadge(booking).tone}`} style={{ marginBottom: 16 }}>
        {bookingBadge(booking).label}
      </span>

      <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
        <button type="button" className="btn btn-danger" disabled={busy} onClick={cancelOne}>
          Cancel this booking
        </button>
        {booking.series_id && (
          <button type="button" className="btn btn-danger" disabled={busy} onClick={cancelSeries}>
            Cancel entire series
          </button>
        )}
      </div>
    </Modal>
  );
}
