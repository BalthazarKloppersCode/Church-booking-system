import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api';

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.adminDashboard().then(setStats);
  }, []);

  if (!stats) return <p>Loading…</p>;

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Dashboard</h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard
          label="Awaiting approval"
          value={stats.pending_approvals}
          accent="var(--amber)"
          link={stats.pending_approvals > 0 ? '/admin/approvals' : null}
        />
        <StatCard label="Bookings this week" value={stats.bookings_this_week} accent="var(--teal)" />
        <StatCard label="Active rooms" value={stats.active_rooms} accent="var(--success)" />
      </div>

      <h2 style={{ fontSize: 18, marginBottom: 14 }}>Next confirmed bookings</h2>
      {stats.next_bookings.length === 0 && <p>Nothing confirmed yet.</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {stats.next_bookings.map((b) => (
          <div key={b.id} className="card" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <strong>{b.room_name}</strong> — {b.congregation}
              <p style={{ fontSize: 13 }}>{new Date(b.start_time).toLocaleString()}</p>
            </div>
            <span className="badge badge-approved">{b.headcount} people</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value, accent, link }) {
  const content = (
    <div className="card">
      <div style={{ fontSize: 34, fontFamily: 'var(--font-display)', color: accent }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{label}</div>
    </div>
  );
  return link ? <Link to={link} style={{ textDecoration: 'none' }}>{content}</Link> : content;
}
