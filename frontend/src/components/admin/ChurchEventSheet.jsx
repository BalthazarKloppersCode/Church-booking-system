import { useState } from 'react';
import { api } from '../../lib/api';
import { formatDay, formatSlot, formatTimeRange } from '../../lib/formatDate';
import SideSheet from './SideSheet';

// Church-calendar events come from Google and know nothing about our rooms.
// This is where an admin says which rooms an event occupies. It's saved against
// the event's series, so for a repeating event it's set once and holds for every
// date — and those rooms then count as taken everywhere in the app.
export default function ChurchEventSheet({ event, rooms, onClose, onSaved }) {
  const [selected, setSelected] = useState(event.roomIds);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [clashes, setClashes] = useState(null);

  function toggle(id) {
    setSelected((current) => (current.includes(id) ? current.filter((r) => r !== id) : [...current, id]));
  }

  async function save() {
    setSaving(true);
    setError('');
    try {
      const result = await api.adminSetEventRooms(event.uid, event.title, selected);
      onSaved();
      if (result.clashes.length) setClashes(result.clashes);
      else onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const unchanged = selected.length === event.roomIds.length && selected.every((id) => event.roomIds.includes(id));

  return (
    <SideSheet title="Church calendar event" onClose={onClose}>
      <h3 style={{ margin: '0 0 4px', fontSize: 18 }}>{event.title}</h3>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--ink-2)' }}>
        {event.allDay ? `${formatDay(event.start)} · all day` : formatSlot(event.start, event.end)}
      </p>
      <p style={{ margin: '4px 0 18px', fontSize: 12, color: 'var(--ink-3)' }}>
        From the church Google Calendar — change its time or title there.
      </p>

      {clashes ? (
        <div>
          <p style={{ margin: '0 0 8px', fontSize: 14, color: 'var(--ink)' }}>
            <strong>Saved.</strong> {clashes.length === 1 ? '1 existing booking overlaps' : `${clashes.length} existing bookings overlap`} this event
            in the next 90 days. Nothing was cancelled — please sort them out:
          </p>
          <ul style={{ margin: '0 0 16px', paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
            {clashes.map((c) => (
              <li key={`${c.booking_id}-${c.event_start}`}>
                <strong>{c.room_name}</strong>, {formatDay(c.start_time)} {formatTimeRange(c.start_time, c.end_time)} — {c.congregation}
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-primary btn-block" onClick={onClose}>Done</button>
        </div>
      ) : (
        <>
          {error && <p style={{ color: 'var(--no)', fontSize: 13, marginBottom: 12 }}>{error}</p>}

          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Rooms this event uses</legend>
            <div style={{ display: 'grid', gap: 2 }}>
              {rooms.map((room) => (
                <label key={room.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 2px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    style={{ width: 'auto' }}
                    checked={selected.includes(room.id)}
                    onChange={() => toggle(room.id)}
                  />
                  <span>{room.name}</span>
                  <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>cap. {room.capacity}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <p style={{ margin: '14px 0 18px', fontSize: 12, color: 'var(--ink-2)' }}>
            Applies to every date this event repeats on, so you only set it once. Chosen rooms can't be booked while the event is on.
            Leave all unticked for an event that doesn't use a bookable room.
          </p>

          <button type="button" className="btn btn-primary btn-block" disabled={saving || unchanged} onClick={save}>
            {saving ? 'Saving…' : selected.length ? 'Save rooms' : 'Save (no rooms)'}
          </button>
        </>
      )}
    </SideSheet>
  );
}
