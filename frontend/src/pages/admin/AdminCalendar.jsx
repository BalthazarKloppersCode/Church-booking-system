import { useEffect, useMemo, useState } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { api } from '../../lib/api';

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { locale: enUS }),
  getDay,
  locales: { 'en-US': enUS },
});

const STATUS_COLOR = {
  approved: '#1B3A6C',
  pending: '#C98A2C',
  external: '#5B6259',
};

const REPEAT_OPTIONS = [
  { value: '', label: "Doesn't repeat" },
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Every 2 weeks' },
  { value: 'monthly', label: 'Monthly' },
];

function pad(n) {
  return String(n).padStart(2, '0');
}

function toDatetimeLocalValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toDateValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

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
  const [congregations, setCongregations] = useState([]);
  const [purposes, setPurposes] = useState([]);

  const [newBookingSlot, setNewBookingSlot] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    api.listRooms().then(setRooms);
    api.listCongregations().then(setCongregations);
    api.listBookingPurposes().then(setPurposes);
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
        status: 'external',
        booking: null,
      }));
      setEvents([...bookingEvents, ...churchEvents]);
    });
  }, [roomFilter, refreshKey]);

  const eventStyleGetter = useMemo(
    () => (event) => ({
      style: {
        backgroundColor: STATUS_COLOR[event.status] || '#5B6259',
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
        <select
          value={roomFilter}
          onChange={(e) => setRoomFilter(e.target.value)}
          style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8 }}
        >
          <option value="">All rooms</option>
          {rooms.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
      </div>
      <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 10 }}>
        Click and drag on an empty slot to add a booking directly — admin-created bookings are
        confirmed instantly and can repeat weekly, every 2 weeks, or monthly.
        {!roomFilter && ' Grey blocks are events already on the church Google Calendar.'}
      </p>
      <div className="card" style={{ padding: 16 }}>
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: 650 }}
          eventPropGetter={eventStyleGetter}
          selectable
          onSelectSlot={(slotInfo) => setNewBookingSlot({ start: slotInfo.start, end: slotInfo.end })}
          onSelectEvent={(event) => {
            if (event.booking) setSelectedEvent(event.booking);
          }}
        />
      </div>

      {newBookingSlot && (
        <NewBookingModal
          slot={newBookingSlot}
          rooms={rooms}
          defaultRoomId={roomFilter}
          congregations={congregations}
          purposes={purposes}
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

function NewBookingModal({ slot, rooms, defaultRoomId, congregations, purposes, onClose, onCreated }) {
  const [form, setForm] = useState({
    room_id: defaultRoomId || '',
    requester_name: '',
    congregation: '',
    email: '',
    phone: '',
    headcount: '',
    purpose: '',
    purpose_other: '',
    is_private_event: false,
    notes: '',
    start: toDatetimeLocalValue(slot.start),
    end: toDatetimeLocalValue(slot.end),
    repeat: '',
    until: toDateValue(slot.start),
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const payload = {
        room_id: form.room_id,
        requester_name: form.requester_name,
        congregation: form.congregation,
        email: form.email,
        phone: form.phone,
        headcount: Number(form.headcount),
        purpose: form.purpose,
        purpose_other: form.purpose === 'Other' ? form.purpose_other : '',
        is_private_event: form.is_private_event,
        notes: form.notes,
        start_time: new Date(form.start).toISOString(),
        end_time: new Date(form.end).toISOString(),
      };
      if (form.repeat) {
        payload.recurrence = {
          frequency: form.repeat,
          // Sent as literal UTC midnight of the picked calendar date, not
          // parsed as local time — otherwise a positive UTC offset (e.g.
          // UTC+2) shifts "until" back to the previous day and silently
          // drops the last valid occurrence.
          until: `${form.until}T00:00:00.000Z`,
        };
      }
      const result = await api.adminCreateBooking(payload);
      onCreated(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="New booking" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12 }}>{error}</p>}

        <div className="field">
          <label>Room</label>
          <select required value={form.room_id} onChange={(e) => setForm({ ...form, room_id: e.target.value })}>
            <option value="" disabled>Select a room</option>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>{r.name} (cap. {r.capacity})</option>
            ))}
          </select>
        </div>

        <div className="field-row">
          <div className="field">
            <label>Start</label>
            <input
              type="datetime-local"
              required
              value={form.start}
              onChange={(e) => setForm({ ...form, start: e.target.value })}
            />
          </div>
          <div className="field">
            <label>End</label>
            <input
              type="datetime-local"
              required
              value={form.end}
              onChange={(e) => setForm({ ...form, end: e.target.value })}
            />
          </div>
        </div>

        <div className="field">
          <label>Repeats</label>
          <select value={form.repeat} onChange={(e) => setForm({ ...form, repeat: e.target.value })}>
            {REPEAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        {form.repeat && (
          <div className="field">
            <label>Until</label>
            <input
              type="date"
              required
              value={form.until}
              onChange={(e) => setForm({ ...form, until: e.target.value })}
            />
          </div>
        )}

        <div className="field">
          <label>Requester name</label>
          <input
            required
            value={form.requester_name}
            onChange={(e) => setForm({ ...form, requester_name: e.target.value })}
          />
        </div>

        <div className="field">
          <label>Congregation / group</label>
          <select
            required
            value={form.congregation}
            onChange={(e) => setForm({ ...form, congregation: e.target.value })}
          >
            <option value="" disabled>Select a congregation / group</option>
            {congregations.map((c) => (
              <option key={c.id} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="field-row">
          <div className="field">
            <label>Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Phone</label>
            <input
              required
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
        </div>

        <div className="field">
          <label>Headcount</label>
          <input
            type="number"
            min="1"
            required
            value={form.headcount}
            onChange={(e) => setForm({ ...form, headcount: e.target.value })}
          />
        </div>

        <div className="field">
          <label>Purpose</label>
          <select required value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}>
            <option value="" disabled>Select a purpose</option>
            {purposes.map((p) => (
              <option key={p.id} value={p.name}>{p.name}</option>
            ))}
          </select>
          {form.purpose === 'Other' && (
            <input
              required
              placeholder="Briefly describe the purpose"
              style={{ marginTop: 8 }}
              value={form.purpose_other}
              onChange={(e) => setForm({ ...form, purpose_other: e.target.value })}
            />
          )}
        </div>

        <div className="field">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              style={{ width: 'auto' }}
              checked={form.is_private_event}
              onChange={(e) => setForm({ ...form, is_private_event: e.target.checked })}
            />
            Private event
          </label>
        </div>

        <div className="field">
          <label>Notes (optional)</label>
          <textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginBottom: 14 }}>
          Admin-created bookings are confirmed instantly — no approval step.
        </p>

        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Creating…' : form.repeat ? 'Create repeating bookings' : 'Create booking'}
        </button>
      </form>
    </Modal>
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
      {error && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
      <p style={{ fontSize: 14, marginBottom: 4 }}>
        <strong>{booking.congregation}</strong> · {booking.headcount} people
      </p>
      <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 4 }}>
        {new Date(booking.start_time).toLocaleString()} – {new Date(booking.end_time).toLocaleTimeString()}
      </p>
      <p style={{ fontSize: 13, marginBottom: 4 }}>{booking.purpose}{booking.purpose_other ? `: ${booking.purpose_other}` : ''}</p>
      <p style={{ fontSize: 13, marginBottom: 16 }}>
        Requested by {booking.requester_name} · {booking.email} · {booking.phone}
      </p>
      <span className={`badge badge-${booking.status}`} style={{ marginBottom: 16, display: 'inline-block' }}>
        {booking.status}
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
