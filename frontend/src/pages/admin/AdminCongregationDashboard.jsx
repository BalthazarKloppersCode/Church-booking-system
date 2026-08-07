import { useEffect, useMemo, useState } from 'react';
import { api } from '../../lib/api';

export default function AdminCongregationDashboard() {
  const [congregations, setCongregations] = useState([]);
  const [selected, setSelected] = useState('');
  const [bookings, setBookings] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listCongregations(false).then(setCongregations);
  }, []);

  useEffect(() => {
    if (!selected) {
      setBookings(null);
      return;
    }
    setLoading(true);
    api
      .listBookings({ congregation: selected })
      .then(setBookings)
      .finally(() => setLoading(false));
  }, [selected]);

  const stats = useMemo(() => {
    if (!bookings) return null;
    const statusCounts = { approved: 0, pending: 0, rejected: 0, cancelled: 0 };
    const roomCounts = {};
    let totalHeadcount = 0;
    bookings.forEach((b) => {
      statusCounts[b.status] = (statusCounts[b.status] || 0) + 1;
      roomCounts[b.room_name] = (roomCounts[b.room_name] || 0) + 1;
      totalHeadcount += b.headcount;
    });
    const mostUsedRoom = Object.entries(roomCounts).sort((a, b) => b[1] - a[1])[0];
    const now = new Date();
    const upcoming = bookings
      .filter((b) => new Date(b.start_time) >= now)
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    const past = bookings
      .filter((b) => new Date(b.start_time) < now)
      .sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
    return { statusCounts, mostUsedRoom, totalHeadcount, upcoming, past };
  }, [bookings]);

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Bookings by congregation</h1>

      <div className="field" style={{ maxWidth: 340, marginBottom: 24 }}>
        <label>Congregation</label>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Select a congregation…</option>
          {congregations.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}{!c.active ? ' (inactive)' : ''}
            </option>
          ))}
        </select>
      </div>

      {loading && <p>Loading…</p>}

      {!loading && selected && stats && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 28 }}>
            <StatTile label="Approved" value={stats.statusCounts.approved} accent="var(--success)" />
            <StatTile label="Pending" value={stats.statusCounts.pending} accent="var(--amber)" />
            <StatTile label="Rejected / cancelled" value={stats.statusCounts.rejected + stats.statusCounts.cancelled} accent="var(--danger)" />
            <StatTile label="Total headcount booked" value={stats.totalHeadcount} accent="var(--teal)" />
          </div>

          <p style={{ marginBottom: 24, fontSize: 14 }}>
            Most-used room: <strong>{stats.mostUsedRoom ? stats.mostUsedRoom[0] : '—'}</strong>
            {stats.mostUsedRoom && ` (${stats.mostUsedRoom[1]} booking${stats.mostUsedRoom[1] === 1 ? '' : 's'})`}
          </p>

          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Upcoming ({stats.upcoming.length})</h2>
          <BookingList bookings={stats.upcoming} empty="No upcoming bookings." />

          <h2 style={{ fontSize: 16, margin: '28px 0 12px' }}>Past ({stats.past.length})</h2>
          <BookingList bookings={stats.past} empty="No past bookings." />
        </>
      )}
    </div>
  );
}

function StatTile({ label, value, accent }) {
  return (
    <div className="card">
      <div style={{ fontSize: 28, fontFamily: 'var(--font-display)', color: accent }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{label}</div>
    </div>
  );
}

function BookingList({ bookings, empty }) {
  if (bookings.length === 0) return <p style={{ fontSize: 14 }}>{empty}</p>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
      {bookings.map((b) => (
        <div key={b.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <strong>{b.room_name}</strong>
            <p style={{ fontSize: 13 }}>
              {new Date(b.start_time).toLocaleString()} · {b.headcount} people · {b.purpose}
            </p>
          </div>
          <span className={`badge badge-${b.status}`}>{b.status}</span>
        </div>
      ))}
    </div>
  );
}
