import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import BookPage from './pages/BookPage';
import MyBookingsPage from './pages/MyBookingsPage';

// Admin-only pages pull in chart.js, react-big-calendar, date-fns, etc. —
// none of that belongs in the bundle a booker downloads just to book a
// room, so it's split into its own lazily-loaded chunk.
const AdminLogin = lazy(() => import('./pages/admin/AdminLogin'));
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout'));
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const AdminBookings = lazy(() => import('./pages/admin/AdminBookings'));
const AdminCalendar = lazy(() => import('./pages/admin/AdminCalendar'));
const AdminRoomGrid = lazy(() => import('./pages/admin/AdminRoomGrid'));
const AdminRooms = lazy(() => import('./pages/admin/AdminRooms'));
const AdminManageLists = lazy(() => import('./pages/admin/AdminManageLists'));
const AdminUsers = lazy(() => import('./pages/admin/AdminUsers'));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div style={{ padding: 40 }}>Loading…</div>}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/book" element={<BookPage />} />
          <Route path="/my-bookings" element={<MyBookingsPage />} />

          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="bookings" element={<AdminBookings />} />
            <Route path="calendar" element={<AdminCalendar />} />
            <Route path="grid" element={<AdminRoomGrid />} />
            <Route path="rooms" element={<AdminRooms />} />
            <Route path="lists" element={<AdminManageLists />} />
            <Route path="users" element={<AdminUsers />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
