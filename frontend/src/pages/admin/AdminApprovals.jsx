import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

export default function AdminApprovals() {
  const [bookings, setBookings] = useState(null);
  const [notes, setNotes] = useState({});
  const [busyId, setBusyId] = useState(null);

  async function load() {
    const data = await api.adminApprovals();
    setBookings(data);
  }

  useEffect(() => {
    load();
  }, []);

  async function decide(id, action) {
    setBusyId(id);
    try {
      if (action === 'approve') await api.adminApprove(id, notes[id] || null);
      else await api.adminReject(id, notes[id] || null);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  if (!bookings) return <p>Loading…</p>;

  return (
    <div>
      <h1 style={{ marginBottom: 8 }}>Approvals</h1>
      <p style={{ marginBottom: 24 }}>
        Bookings more than two weeks out, or marked as private events, wait here for a decision.
      </p>

      {bookings.length === 0 && <p>Nothing waiting on you right now.</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {bookings.map((b) => (
          <div key={b.id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <div>
                <h3 style={{ fontSize: 17 }}>{b.room_name}</h3>
                <p style={{ fontSize: 13 }}>
                  {new Date(b.start_time).toLocaleString()} – {new Date(b.end_time).toLocaleTimeString()}
                </p>
              </div>
              {b.is_private_event && <span className="badge badge-pending">Private event</span>}
            </div>
            <p style={{ fontSize: 14 }}>
              <strong>{b.requester_name}</strong> ({b.congregation}) · {b.headcount} people
            </p>
            <p style={{ fontSize: 14 }}>{b.purpose}</p>
            {b.notes && <p style={{ fontSize: 13, fontStyle: 'italic' }}>Note: {b.notes}</p>}
            <p style={{ fontSize: 12 }}>{b.email} · {b.phone}</p>

            <input
              placeholder="Optional note to include in the response"
              value={notes[b.id] || ''}
              onChange={(e) => setNotes({ ...notes, [b.id]: e.target.value })}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 8, margin: '10px 0' }}
            />

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="btn btn-primary"
                disabled={busyId === b.id}
                onClick={() => decide(b.id, 'approve')}
              >
                Approve
              </button>
              <button
                className="btn btn-danger"
                disabled={busyId === b.id}
                onClick={() => decide(b.id, 'reject')}
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
