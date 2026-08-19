import { Link } from 'react-router-dom';

export default function HomePage() {
  const bookerToken = localStorage.getItem('booker_token');
  const bookerUser = (() => {
    try {
      return JSON.parse(localStorage.getItem('booker_user') || 'null');
    } catch {
      return null;
    }
  })();

  function handleLogout() {
    localStorage.removeItem('booker_token');
    localStorage.removeItem('booker_user');
    window.location.reload();
  }

  return (
    <div className="container" style={{ maxWidth: 620, paddingTop: 100 }}>
      <div className="eyebrow">Pinehurst Campus</div>
      <h1 style={{ fontSize: 40, marginBottom: 14 }}>Find a room, book a room.</h1>
      <p style={{ fontSize: 16, marginBottom: 36 }}>
        Book classrooms, the training hall, the main hall, the coffee shop, or the lounge for
        your congregation, group, or event. Bookings up to two weeks out are confirmed
        instantly — anything further ahead, or a private event, goes to the admin office for
        a quick approval.
      </p>

      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Link to="/book" className="btn btn-primary" style={{ fontSize: 15, padding: '14px 26px' }}>
          Book a room
        </Link>
        <Link to="/my-bookings" className="btn btn-secondary" style={{ fontSize: 15, padding: '14px 26px' }}>
          View my bookings
        </Link>
      </div>

      {bookerToken && (
        <p style={{ marginTop: 20, fontSize: 13, color: 'var(--ink-soft)' }}>
          Logged in{bookerUser?.name ? ` as ${bookerUser.name}` : ''} ·{' '}
          <button
            type="button"
            onClick={handleLogout}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              font: 'inherit',
              color: 'inherit',
              textDecoration: 'underline',
              cursor: 'pointer',
            }}
          >
            Log out
          </button>
        </p>
      )}

      <div style={{ marginTop: 64, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
        <Link to="/admin/login" style={{ fontSize: 13, color: 'var(--ink-soft)' }}>
          Admin office login →
        </Link>
      </div>
    </div>
  );
}
