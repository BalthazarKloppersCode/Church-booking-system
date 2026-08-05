import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';

export default function MyBookingsPage() {
  const [email, setEmail] = useState('');
  const [bookings, setBookings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLookup(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const results = await api.listBookings({ email });
      setBookings(results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel(id) {
    if (!confirm('Cancel this booking?')) return;
    try {
      await api.cancelBooking(id, email);
      const results = await api.listBookings({ email });
      setBookings(results);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <div className="eyebrow">
        <Link to="/" style={{ color: 'inherit' }}>← Back home</Link>
      </div>
      <h1 style={{ marginBottom: 24 }}>My bookings</h1>

      <form className="card" onSubmit={handleLookup} style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        <input
          type="email"
          required
          placeholder="Enter the email you booked with"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ flex: 1, padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 8 }}
        />
        <button className="btn btn-primary" disabled={loading}>
          {loading ? 'Looking up…' : 'Look up'}
        </button>
      </form>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {bookings && bookings.length === 0 && <p>No bookings found for that email.</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {bookings?.map((b) => (
          <div key={b.id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h3 style={{ fontSize: 17 }}>{b.room_name}</h3>
                <p style={{ fontSize: 13 }}>
                  {new Date(b.start_time).toLocaleString()} – {new Date(b.end_time).toLocaleTimeString()}
                </p>
                <p style={{ fontSize: 13 }}>{b.purpose}</p>
              </div>
              <span className={`badge badge-${b.status}`}>{b.status}</span>
            </div>
            {(b.status === 'pending' || b.status === 'approved') && (
              <button className="btn btn-danger" style={{ marginTop: 10 }} onClick={() => handleCancel(b.id)}>
                Cancel booking
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
