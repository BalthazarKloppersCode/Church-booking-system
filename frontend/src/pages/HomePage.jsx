import { Link } from 'react-router-dom';

export default function HomePage() {
  return (
    <div className="container" style={{ maxWidth: 620, paddingTop: 100 }}>
      <div className="eyebrow">Campus room booking</div>
      <h1 style={{ fontSize: 40, marginBottom: 14 }}>Find a room, book a room.</h1>
      <p style={{ fontSize: 16, marginBottom: 36 }}>
        Book classrooms, training halls, or the main hall for your congregation, group, or
        event. Bookings up to two weeks out are confirmed instantly — anything further ahead,
        or a private event, goes to the admin office for a quick approval.
      </p>

      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Link to="/book" className="btn btn-primary" style={{ fontSize: 15, padding: '14px 26px' }}>
          Book a room
        </Link>
        <Link to="/my-bookings" className="btn btn-secondary" style={{ fontSize: 15, padding: '14px 26px' }}>
          View my bookings
        </Link>
      </div>

      <div style={{ marginTop: 64, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
        <Link to="/admin/login" style={{ fontSize: 13, color: 'var(--ink-soft)' }}>
          Admin office login →
        </Link>
      </div>
    </div>
  );
}
