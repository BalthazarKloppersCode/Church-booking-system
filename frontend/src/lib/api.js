const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = localStorage.getItem('admin_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function bookerAuthHeaders() {
  const token = localStorage.getItem('booker_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Rooms
  listRooms: () => request('/api/rooms'),
  suggestRooms: (payload) =>
    request('/api/rooms/suggest', { method: 'POST', body: JSON.stringify(payload) }),
  createRoom: (payload) => request('/api/rooms', { method: 'POST', body: JSON.stringify(payload) }),
  updateRoom: (id, payload) =>
    request(`/api/rooms/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateRoom: (id) => request(`/api/rooms/${id}`, { method: 'DELETE' }),

  // Congregations
  listCongregations: (activeOnly = true, areaId = null) =>
    request(`/api/congregations?active_only=${activeOnly}${areaId ? `&area_id=${areaId}` : ''}`),
  createCongregation: (payload) =>
    request('/api/congregations', { method: 'POST', body: JSON.stringify(payload) }),
  updateCongregation: (id, payload) =>
    request(`/api/congregations/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateCongregation: (id) => request(`/api/congregations/${id}`, { method: 'DELETE' }),

  // Booking purposes
  listBookingPurposes: (activeOnly = true) =>
    request(`/api/booking-purposes?active_only=${activeOnly}`),
  createBookingPurpose: (payload) =>
    request('/api/booking-purposes', { method: 'POST', body: JSON.stringify(payload) }),
  updateBookingPurpose: (id, payload) =>
    request(`/api/booking-purposes/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateBookingPurpose: (id) => request(`/api/booking-purposes/${id}`, { method: 'DELETE' }),

  // Areas
  listAreas: (activeOnly = true) => request(`/api/areas?active_only=${activeOnly}`),
  createArea: (payload) => request('/api/areas', { method: 'POST', body: JSON.stringify(payload) }),
  updateArea: (id, payload) =>
    request(`/api/areas/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateArea: (id) => request(`/api/areas/${id}`, { method: 'DELETE' }),

  // Booker users (admin-managed) + booker login
  listUsers: () => request('/api/admin/users'),
  createUser: (payload) => request('/api/admin/users', { method: 'POST', body: JSON.stringify(payload) }),
  updateUser: (id, payload) =>
    request(`/api/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteUser: (id) => request(`/api/admin/users/${id}`, { method: 'DELETE' }),
  bookerLogin: (payload) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) }),

  // Bookings
  createBooking: (payload) =>
    request('/api/bookings', { method: 'POST', body: JSON.stringify(payload), headers: bookerAuthHeaders() }),
  listBookings: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/bookings${qs ? `?${qs}` : ''}`);
  },
  cancelBooking: (id, email) =>
    request(`/api/bookings/${id}/cancel?email=${encodeURIComponent(email)}`, { method: 'POST' }),

  // Admin
  adminRegister: (payload) =>
    request('/api/admin/register', { method: 'POST', body: JSON.stringify(payload) }),
  adminLogin: (payload) =>
    request('/api/admin/login', { method: 'POST', body: JSON.stringify(payload) }),
  adminMe: () => request('/api/admin/me'),
  adminApprovals: () => request('/api/admin/approvals'),
  adminApprove: (id, admin_note) =>
    request(`/api/admin/bookings/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ admin_note }),
    }),
  adminReject: (id, admin_note) =>
    request(`/api/admin/bookings/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ admin_note }),
    }),
  adminDashboard: () => request('/api/admin/dashboard'),
  adminAnalytics: (days) => request(`/api/admin/analytics?days=${days}`),
  adminCreateBooking: (payload) =>
    request('/api/admin/bookings', { method: 'POST', body: JSON.stringify(payload) }),
  adminCancelBooking: (id) => request(`/api/admin/bookings/${id}/cancel`, { method: 'POST' }),
  adminCancelSeries: (seriesId) =>
    request(`/api/admin/bookings/series/${seriesId}/cancel`, { method: 'POST' }),
  adminUpdateBooking: (id, payload) =>
    request(`/api/admin/bookings/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  adminDeleteBooking: (id) => request(`/api/admin/bookings/${id}`, { method: 'DELETE' }),
};
