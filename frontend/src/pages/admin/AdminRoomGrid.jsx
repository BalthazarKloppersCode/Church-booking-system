import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function AdminRoomGrid() {
  const [date, setDate] = useState(todayStr());
  const [rooms, setRooms] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const dayStart = new Date(`${date}T00:00:00`).toISOString();
      const dayEnd = new Date(`${date}T23:59:59`).toISOString();
      const [roomList, dayBookings] = await Promise.all([
        api.listRooms(),
        api.listBookings({ start_after: dayStart, start_before: dayEnd }),
      ]);
      setRooms(roomList);
      setBookings(dayBookings.filter((b) => b.status === 'approved' || b.status === 'pending'));
      setLoading(false);
    }
    load();
  }, [date]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1>Room grid</h1>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8 }}
        />
      </div>

      {loading && <p>Loading…</p>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
        {rooms.map((room) => {
          const roomBookings = bookings
            .filter((b) => b.room_id === room.id)
            .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

          return (
            <div key={room.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <h3 style={{ fontSize: 16 }}>{room.name}</h3>
                <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Cap. {room.capacity}</span>
              </div>

              {roomBookings.length === 0 ? (
                <span className="badge badge-approved">Free all day</span>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {roomBookings.map((b) => (
                    <div
                      key={b.id}
                      style={{
                        fontSize: 13,
                        padding: '6px 10px',
                        borderRadius: 6,
                        background: b.status === 'pending' ? 'var(--amber-tint)' : 'var(--teal-tint)',
                      }}
                    >
                      <strong>
                        {new Date(b.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}–
                        {new Date(b.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </strong>{' '}
                      {b.congregation}
                      {b.status === 'pending' ? ' (pending)' : ''}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
