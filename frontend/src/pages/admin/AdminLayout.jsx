import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAdmin, logoutAdmin } from '../../lib/useAdmin';

const NAV_ITEMS = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/bookings', label: 'Bookings' },
  { to: '/admin/grid', label: 'Room grid' },
  { to: '/admin/calendar', label: 'Calendar' },
  { to: '/admin/rooms', label: 'Manage rooms' },
  { to: '/admin/lists', label: 'Manage lists' },
  { to: '/admin/users', label: 'Manage users' },
];

export default function AdminLayout() {
  const { admin, loading } = useAdmin();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      return localStorage.getItem('admin_sidebar_open') !== 'false';
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('admin_sidebar_open', String(sidebarOpen));
    } catch {
      // ignore — collapse preference just won't persist
    }
  }, [sidebarOpen]);

  if (loading) return <div className="container">Loading…</div>;
  if (!admin) return null;

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside
        style={{
          width: sidebarOpen ? 220 : 56,
          flexShrink: 0,
          background: 'var(--teal-dark)',
          color: 'white',
          padding: sidebarOpen ? '28px 18px' : '28px 8px',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.15s ease',
          overflow: 'hidden',
        }}
      >
        <button
          className="btn btn-ghost"
          style={{
            color: 'white',
            padding: '4px 8px',
            minWidth: 0,
            alignSelf: sidebarOpen ? 'flex-end' : 'center',
            marginBottom: sidebarOpen ? 10 : 20,
          }}
          onClick={() => setSidebarOpen((open) => !open)}
          title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
        >
          {sidebarOpen ? '«' : '»'}
        </button>

        {sidebarOpen && (
          <>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, marginBottom: 20, whiteSpace: 'nowrap' }}>
              Pinehurst Admin
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
                    whiteSpace: 'nowrap',
                  })}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 10, whiteSpace: 'nowrap' }}>{admin.name}</div>
            <button
              className="btn btn-ghost"
              style={{ color: 'white', justifyContent: 'flex-start', padding: '8px 12px', whiteSpace: 'nowrap' }}
              onClick={() => logoutAdmin(navigate)}
            >
              Log out
            </button>
          </>
        )}
      </aside>
      <main style={{ flex: 1, padding: '32px 40px', minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
