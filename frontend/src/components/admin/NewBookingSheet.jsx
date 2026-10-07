import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import DatePicker from '../fields/DatePicker';
import DateTimeField from '../fields/DateTimeField';
import Select from '../fields/Select';
import SideSheet from './SideSheet';

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

// The next whole hour, for when the sheet is opened without a calendar slot.
function defaultSlot() {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(start.getHours() + 1);
  return { start, end: new Date(start.getTime() + 60 * 60 * 1000) };
}

// Admin-created bookings skip approval entirely. Loads its own pick-lists so it
// can be opened from anywhere (the calendar, the bookings page).
export default function NewBookingSheet({ slot, defaultRoomId, onClose, onCreated }) {
  const [initialSlot] = useState(() => slot || defaultSlot());
  const [rooms, setRooms] = useState([]);
  const [congregations, setCongregations] = useState([]);
  const [purposes, setPurposes] = useState([]);
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
    start: toDatetimeLocalValue(initialSlot.start),
    end: toDatetimeLocalValue(initialSlot.end),
    repeat: '',
    until: toDateValue(initialSlot.start),
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listRooms().then(setRooms);
    api.listCongregations().then(setCongregations);
    api.listBookingPurposes().then(setPurposes);
  }, []);

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
    <SideSheet title="New booking" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <p style={{ color: 'var(--no)', fontSize: 13, marginBottom: 12 }}>{error}</p>}

        <div className="field">
          <label>Room</label>
          <Select size="admin" aria-label="Room" required value={form.room_id} onChange={(e) => setForm({ ...form, room_id: e.target.value })}>
            <option value="" disabled>Select a room</option>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>{r.name} (cap. {r.capacity})</option>
            ))}
          </Select>
        </div>

        <div className="field">
          <label>Start</label>
          <DateTimeField required value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} />
        </div>
        <div className="field">
          <label>End</label>
          <DateTimeField required value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} />
        </div>

        <div className="field">
          <label>Repeats</label>
          <Select size="admin" aria-label="Repeats" value={form.repeat} onChange={(e) => setForm({ ...form, repeat: e.target.value })}>
            {REPEAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
        </div>
        {form.repeat && (
          <div className="field">
            <label>Until</label>
            <DatePicker
              size="admin"
              required
              aria-label="Until"
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
          <Select
            size="admin"
            aria-label="Congregation / group"
            required
            value={form.congregation}
            onChange={(e) => setForm({ ...form, congregation: e.target.value })}
          >
            <option value="" disabled>Select a congregation / group</option>
            {congregations.map((c) => (
              <option key={c.id} value={c.name}>{c.name}</option>
            ))}
          </Select>
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
          <Select size="admin" aria-label="Purpose" required value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}>
            <option value="" disabled>Select a purpose</option>
            {purposes.map((p) => (
              <option key={p.id} value={p.name}>{p.name}</option>
            ))}
          </Select>
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

        <p style={{ fontSize: 12, color: 'var(--ink-2)', marginBottom: 14 }}>
          Admin-created bookings are confirmed instantly — no approval step.
        </p>

        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Creating…' : form.repeat ? 'Create repeating bookings' : 'Create booking'}
        </button>
      </form>
    </SideSheet>
  );
}
