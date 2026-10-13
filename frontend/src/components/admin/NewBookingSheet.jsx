import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import DatePicker from '../fields/DatePicker';
import DateTimeField from '../fields/DateTimeField';
import Select from '../fields/Select';
import SideSheet from './SideSheet';
import { countOccurrences, defaultUntil } from '../../lib/recurrence';

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
    room_ids: defaultRoomId ? [defaultRoomId] : [],
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

  function toggleRoom(id) {
    setForm((f) => ({
      ...f,
      room_ids: f.room_ids.includes(id) ? f.room_ids.filter((r) => r !== id) : [...f.room_ids, id],
    }));
  }

  // Picking a repeat starts "Until" three months out — it used to start on the
  // first booking's own date, which quietly made a "repeat" of just one booking.
  function chooseRepeat(repeat) {
    setForm((f) => {
      const firstDay = f.start.slice(0, 10);
      return { ...f, repeat, until: repeat && f.until <= firstDay ? defaultUntil(firstDay) : f.until };
    });
  }

  const repeatCount = form.repeat ? countOccurrences(form.start.slice(0, 10), form.until, form.repeat) : 1;
  const chosenRooms = rooms.filter((r) => form.room_ids.includes(r.id));
  const totalCapacity = chosenRooms.reduce((sum, r) => sum + r.capacity, 0);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (!form.room_ids.length) {
      setError('Choose at least one room.');
      return;
    }
    if (form.repeat && repeatCount < 2) {
      setError('Choose an "Until" date after the first booking — otherwise only one booking is made.');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        room_ids: form.room_ids,
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

        <fieldset className="field" style={{ border: 0, padding: 0, margin: '0 0 16px' }}>
          <legend style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, padding: 0 }}>
            Rooms{chosenRooms.length > 1 ? ` · ${chosenRooms.length} selected` : ''}
          </legend>
          <div
            style={{
              display: 'grid',
              gap: 0,
              maxHeight: 190,
              overflowY: 'auto',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: '4px 10px',
              background: 'var(--paper)',
            }}
          >
            {rooms.map((r) => (
              <label key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer' }}>
                <input type="checkbox" style={{ width: 'auto' }} checked={form.room_ids.includes(r.id)} onChange={() => toggleRoom(r.id)} />
                <span>{r.name}</span>
                <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>cap. {r.capacity}</span>
              </label>
            ))}
          </div>
          <p className="field-hint" style={{ margin: '6px 0 0' }}>
            {chosenRooms.length > 1
              ? `Each room is booked for the same time, and the headcount only has to fit them together (${totalCapacity} seats).`
              : 'Tick more than one room if the same event uses several.'}
          </p>
        </fieldset>

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
          <Select size="admin" aria-label="Repeats" value={form.repeat} onChange={(e) => chooseRepeat(e.target.value)}>
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
            <p className="field-hint" style={{ margin: '6px 0 0', color: repeatCount < 2 ? 'var(--no)' : undefined }}>
              {repeatCount < 2
                ? 'Pick a date after the first booking.'
                : `Creates ${repeatCount} bookings, ${form.repeat === 'monthly' ? 'one a month' : form.repeat === 'biweekly' ? 'one every 2 weeks' : 'one a week'}.`}
            </p>
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
          {submitting ? 'Creating…' : form.repeat ? `Create ${repeatCount} bookings` : chosenRooms.length > 1 ? `Create booking for ${chosenRooms.length} rooms` : 'Create booking'}
        </button>
      </form>
    </SideSheet>
  );
}
