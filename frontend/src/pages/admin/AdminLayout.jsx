import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAdmin, logoutAdmin } from '../../lib/useAdmin';

const NAV_ITEMS = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/approvals', label: 'Approvals' },
  { to: '/admin/grid', label: 'Room grid' },
  { to: '/admin/calendar', label: 'Calendar' },
  { to: '/admin/rooms', label: 'Manage rooms' },
];

export default function AdminLayout() {
  const { admin, loading } = useAdmin();
  const navigate = useNavigate();

  if (loading) return <div className="container">Loading…</div>;
  if (!admin) return null;

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside
        style={{
          width: 220,
          background: 'var(--teal-dark)',
          color: 'white',
          padding: '28px 18px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, marginBottom: 30 }}>
          Campus Admin
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => ({
                padding: '10px 12px',
                borderRadius: 8,
                color: 'white',
                fontSize: 14,
                fontWeight: isActive ? 700 : 500,
                background: isActive ? 'rgba(255,255,255,0.14)' : 'transparent',
                textDecoration: 'none',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 10 }}>{admin.name}</div>
        <button
          className="btn btn-ghost"
          style={{ color: 'white', justifyContent: 'flex-start', padding: '8px 12px' }}
          onClick={() => logoutAdmin(navigate)}
        >
          Log out
        </button>
      </aside>
      <main style={{ flex: 1, padding: '32px 40px' }}>
        <Outlet />
      </main>
    </div>
  );
}
