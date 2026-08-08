import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import BookPage from './pages/BookPage';
import MyBookingsPage from './pages/MyBookingsPage';
import AdminLogin from './pages/admin/AdminLogin';
import AdminLayout from './pages/admin/AdminLayout';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminApprovals from './pages/admin/AdminApprovals';
import AdminCalendar from './pages/admin/AdminCalendar';
import AdminRoomGrid from './pages/admin/AdminRoomGrid';
import AdminRooms from './pages/admin/AdminRooms';
import AdminManageLists from './pages/admin/AdminManageLists';
import AdminCongregationDashboard from './pages/admin/AdminCongregationDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/book" element={<BookPage />} />
        <Route path="/my-bookings" element={<MyBookingsPage />} />

        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="approvals" element={<AdminApprovals />} />
          <Route path="calendar" element={<AdminCalendar />} />
          <Route path="grid" element={<AdminRoomGrid />} />
          <Route path="rooms" element={<AdminRooms />} />
          <Route path="lists" element={<AdminManageLists />} />
          <Route path="congregations/dashboard" element={<AdminCongregationDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
