import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatDay, formatTimeRange } from '../lib/formatDate';
import { bookingBadge } from '../lib/bookingStatus';
import BookingConfirmation from '../components/BookingConfirmation';

// Two ways in, and neither lists other people's bookings:
//  - logged in: your own bookings are listed straight away;
//  - not logged in (for example you used the private-events link): give the email
//    the booking was made with AND its reference, from the confirmation or the
//    WhatsApp message. An email address on its own shows nothing.
export default function MyBookingsPage() {
  const [loggedIn, setLoggedIn] = useState(() => {
    try {
      return Boolean(localStorage.getItem('booker_token'));
    } catch {
      return false;
    }
  });
  const [email, setEmail] = useState('');
  const [reference, setReference] = useState('');
  const [bookings, setBookings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);
  const [findOpen, setFindOpen] = useState(false);

  async function loadMine() {
    setLoading(true);
    setError('');
    try {
      setBookings(await api.listMyBookings());
    } catch (err) {
      if (/log in/i.test(err.message)) {
        // An expired login: drop it and fall back to finding a booking by email and reference.
        try {
          localStorage.removeItem('booker_token');
          localStorage.removeItem('booker_user');
        } catch {
          // ignore
        }
        setLoggedIn(false);
        setError('Your login has expired. Log in again, or find a booking with its email and reference below.');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (loggedIn) loadMine();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on arrival
  }, []);

  async function handleFind(e) {
    e?.preventDefault();
    setLoading(true);
    setError('');
    setBookings(null);
    setOpenId(null);
    try {
      setBookings(await api.findMyBooking(email.trim(), reference.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel(id) {
    if (!confirm('Cancel this booking?')) return;
    try {
      await api.cancelBooking(id, loggedIn && !findOpen ? '' : email.trim());
      if (loggedIn && !findOpen) await loadMine();
      else await handleFind();
    } catch (err) {
      setError(err.message);
    }
  }

  const byReference = !loggedIn || findOpen;
  // What proves it is yours: the account when logged in, otherwise the email that was typed to find it.
  const proof = loggedIn && !findOpen ? '' : email.trim();

  const findForm = (
    <form className="card" onSubmit={handleFind} style={{ marginBottom: 24 }}>
      <div className="field">
        <label>Email the booking was made with</label>
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="field">
        <label>Booking reference</label>
        <input required placeholder="JGP-1A2B3C4D" value={reference} onChange={(e) => setReference(e.target.value)} />
        <span className="field-hint">You'll find it on your confirmation and in your WhatsApp message.</span>
      </div>
      <button className="btn btn-primary" disabled={loading}>{loading ? 'Looking…' : 'Find my booking'}</button>
    </form>
  );

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <div className="eyebrow">
        <Link to="/" style={{ color: 'inherit' }}>← Back home</Link>
      </div>
      <h1 style={{ marginBottom: 24 }}>My bookings</h1>

      {error && <p role="alert" style={{ color: 'var(--no)' }}>{error}</p>}

      {byReference ? (
        <>
          {loggedIn && (
            <p style={{ fontSize: 14 }}>
              <button type="button" className="btn btn-ghost" style={{ padding: 0, height: 'auto', textDecoration: 'underline' }} onClick={() => { setFindOpen(false); loadMine(); }}>
                ← Back to my bookings
              </button>
            </p>
          )}
          {findForm}
          {!loggedIn && (
            <p style={{ fontSize: 13, marginBottom: 20 }}>
              Have an account? <Link to="/book">Log in</Link> and your bookings are listed here.
            </p>
          )}
        </>
      ) : (
        <p style={{ fontSize: 14, marginBottom: 16 }}>
          Showing the bookings made with your account.{' '}
          <button type="button" className="btn btn-ghost" style={{ padding: 0, height: 'auto', textDecoration: 'underline' }} onClick={() => { setFindOpen(true); setBookings(null); }}>
            Find a booking by its reference
          </button>
        </p>
      )}

      {loading && !bookings && <p>Looking…</p>}
      {bookings && bookings.length === 0 && <p>No bookings to show yet.</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {bookings?.map((b) => (
          <div key={b.id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
              <div>
                <h3 style={{ fontSize: 17 }}>{b.room_name}</h3>
                <p style={{ fontSize: 13 }}>
                  {formatDay(b.start_time)} · {formatTimeRange(b.start_time, b.end_time)}
                </p>
                <p style={{ fontSize: 13 }}>{b.purpose_other ? `${b.purpose}: ${b.purpose_other}` : b.purpose}</p>
                <p style={{ fontSize: 12, color: 'var(--ink-3)', margin: 0 }}>Reference {b.reference}</p>
              </div>
              <span className={`badge badge-${bookingBadge(b).tone}`}>{bookingBadge(b).label}</span>
            </div>
            {b.status === 'rejected' && b.admin_note && (
              <p style={{ fontSize: 13, color: 'var(--no)', margin: '8px 0 0' }}>{b.admin_note}</p>
            )}
            {(b.status === 'pending' || b.status === 'approved') && (
              <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
                <button className="btn btn-secondary" onClick={() => setOpenId(openId === b.id ? null : b.id)}>
                  {openId === b.id ? 'Hide confirmation' : 'View & save confirmation'}
                </button>
                <button className="btn btn-danger" onClick={() => handleCancel(b.id)}>
                  Cancel booking
                </button>
              </div>
            )}
            {openId === b.id && <BookingConfirmation bookingId={b.id} email={proof} />}
          </div>
        ))}
      </div>
    </div>
  );
}
