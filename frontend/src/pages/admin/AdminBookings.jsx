import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import DateTimeField from '../../components/fields/DateTimeField';
import Select from '../../components/fields/Select';
import BookingRow from '../../components/admin/BookingRow';
import NewBookingSheet from '../../components/admin/NewBookingSheet';
import PendingRow from '../../components/admin/PendingRow';

function pad(n) {
  return String(n).padStart(2, '0');
}

function toDatetimeLocalValue(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const SORT_OPTIONS = [
  { value: 'start_time', label: 'Date booking is for' },
  { value: 'created_at', label: 'Date booking was made' },
  { value: 'congregation', label: 'Congregation' },
];

function sortBookings(bookings, sortKey, sortDir) {
  const dir = sortDir === 'asc' ? 1 : -1;
  return bookings.slice().sort((a, b) => {
    if (sortKey === 'congregation') {
      return a.congregation.localeCompare(b.congregation) * dir;
    }
    return (new Date(a[sortKey]) - new Date(b[sortKey])) * dir;
  });
}

function SortBar({ sortKey, setSortKey, sortDir, setSortDir }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}>
      <label style={{ fontSize: 13, color: 'var(--ink-2)' }}>Sort by</label>
      <Select size="admin" aria-label="Sort by" value={sortKey} onChange={(e) => setSortKey(e.target.value)} style={{ minWidth: 220 }}>
        {SORT_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </Select>
      <button
        type="button"
        className="btn btn-secondary"
        style={{ padding: '6px 12px', fontSize: 12 }}
        onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
      >
        {sortDir === 'asc' ? '↑ Oldest first' : '↓ Newest first'}
      </button>
    </div>
  );
}

export default function AdminBookings() {
  const [tab, setTab] = useState('all');
  const [bookings, setBookings] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [pending, setPending] = useState(null);
  const [newOpen, setNewOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [error, setError] = useState('');
  const [sortKey, setSortKey] = useState('start_time');
  const [sortDir, setSortDir] = useState('desc');

  async function loadAll() {
    const [all, rms] = await Promise.all([api.listBookings({}), api.listRooms()]);
    setBookings(all);
    setRooms(rms);
  }

  async function loadPending() {
    setPending(await api.adminApprovals());
  }

  useEffect(() => {
    loadAll();
    loadPending();
  }, []);

  const now = new Date();
  const archived = (bookings || []).filter(
    (b) => b.status === 'cancelled' || b.status === 'rejected' || new Date(b.end_time) < now
  );
  const active = (bookings || []).filter((b) => !archived.includes(b));

  async function decide(id, action, note = null) {
    setBusyId(id);
    try {
      if (action === 'approve') await api.adminApprove(id, note);
      else await api.adminReject(id, note);
      await Promise.all([loadAll(), loadPending()]);
    } finally {
      setBusyId(null);
    }
  }

  async function cancelBooking(id) {
    if (!confirm('Cancel this booking?')) return;
    setBusyId(id);
    try {
      await api.adminCancelBooking(id);
      await Promise.all([loadAll(), loadPending()]);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteBooking(id) {
    if (!confirm('Permanently delete this booking? This cannot be undone.')) return;
    setBusyId(id);
    try {
      await api.adminDeleteBooking(id);
      await Promise.all([loadAll(), loadPending()]);
    } finally {
      setBusyId(null);
    }
  }

  function startEdit(b) {
    setEditingId(b.id);
    setError('');
    setEditForm({
      room_id: b.room_id,
      requester_name: b.requester_name,
      congregation: b.congregation,
      email: b.email,
      phone: b.phone,
      headcount: b.headcount,
      purpose: b.purpose,
      notes: b.notes || '',
      status: b.status,
      start_time: toDatetimeLocalValue(b.start_time),
      end_time: toDatetimeLocalValue(b.end_time),
    });
  }

  async function saveEdit(id) {
    setError('');
    setBusyId(id);
    try {
      await api.adminUpdateBooking(id, {
        ...editForm,
        headcount: Number(editForm.headcount),
        start_time: new Date(editForm.start_time).toISOString(),
        end_time: new Date(editForm.end_time).toISOString(),
      });
      setEditingId(null);
      await Promise.all([loadAll(), loadPending()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>Bookings</h1>
        {pending?.length > 0 && (
          <span style={{ fontSize: 14, color: 'var(--ink-2)' }}>{pending.length} awaiting your approval</span>
        )}
        <div style={{ flex: 1 }} />
        <button type="button" className="btn btn-secondary" style={{ height: 36 }} onClick={() => setNewOpen(true)}>
          New booking
        </button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {[
          ['all', 'All bookings'],
          ['approvals', `Approvals${pending?.length ? ` (${pending.length})` : ''}`],
          ['archive', 'Archive'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <SortBar sortKey={sortKey} setSortKey={setSortKey} sortDir={sortDir} setSortDir={setSortDir} />

      {tab === 'all' && (
        <BookingList
          bookings={bookings ? sortBookings(active, sortKey, sortDir) : []}
          bookingsLoaded={!!bookings}
          rooms={rooms}
          busyId={busyId}
          editingId={editingId}
          editForm={editForm}
          setEditForm={setEditForm}
          error={error}
          onEdit={startEdit}
          onCancelEdit={() => setEditingId(null)}
          onSaveEdit={saveEdit}
          onCancelBooking={cancelBooking}
          onDeleteBooking={deleteBooking}
          onApprove={(id) => decide(id, 'approve')}
          onReject={(id, note) => decide(id, 'reject', note)}
          emptyText="No active bookings."
        />
      )}

      {tab === 'approvals' && (
        <ApprovalsTab
          bookings={pending ? sortBookings(pending, sortKey, sortDir) : null}
          busyId={busyId}
          onApprove={(id) => decide(id, 'approve')}
          onReject={(id, note) => decide(id, 'reject', note)}
        />
      )}

      {tab === 'archive' && (
        <BookingList
          bookings={bookings ? sortBookings(archived, sortKey, sortDir) : []}
          bookingsLoaded={!!bookings}
          rooms={rooms}
          busyId={busyId}
          editingId={null}
          readOnly
          onDeleteBooking={deleteBooking}
          emptyText="Nothing archived yet."
        />
      )}

      {newOpen && (
        <NewBookingSheet
          onClose={() => setNewOpen(false)}
          onCreated={() => {
            setNewOpen(false);
            loadAll();
            loadPending();
          }}
        />
      )}
    </div>
  );
}

function ApprovalsTab({ bookings, busyId, onApprove, onReject }) {
  if (!bookings) return <p>Loading…</p>;
  return (
    <div>
      <p style={{ marginBottom: 20 }}>
        Bookings more than two weeks out, marked as private events, or from areas that always
        need approval, wait here for a decision.
      </p>
      {bookings.length === 0 && <p>Nothing waiting on you right now.</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {bookings.map((b) => (
          <PendingRow key={b.id} booking={b} busy={busyId === b.id} onApprove={onApprove} onReject={onReject} />
        ))}
      </div>
    </div>
  );
}

function BookingList({
  bookings,
  bookingsLoaded,
  rooms,
  busyId,
  editingId,
  editForm,
  setEditForm,
  error,
  onEdit,
  onCancelEdit,
  onSaveEdit,
  onCancelBooking,
  onDeleteBooking,
  onApprove,
  onReject,
  readOnly,
  emptyText,
}) {
  if (!bookingsLoaded) return <p>Loading…</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {bookings.length === 0 && <p>{emptyText}</p>}
      {bookings.map((b) =>
          editingId === b.id ? (
            <div key={b.id} className="card">
              {error && <p style={{ color: 'var(--no)', fontSize: 13, marginBottom: 10 }}>{error}</p>}
              <div className="field-row">
                <div className="field">
                  <label>Room</label>
                  <Select size="admin" value={editForm.room_id} onChange={(e) => setEditForm({ ...editForm, room_id: e.target.value })}>
                    {rooms.map((r) => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </Select>
                </div>
                <div className="field">
                  <label>Status</label>
                  <Select size="admin" value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
                    <option value="pending">Awaiting the office</option>
                    <option value="approved">Confirmed</option>
                    <option value="rejected">Declined</option>
                    <option value="cancelled">Cancelled</option>
                  </Select>
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Start</label>
                  <DateTimeField value={editForm.start_time} onChange={(e) => setEditForm({ ...editForm, start_time: e.target.value })} />
                </div>
                <div className="field">
                  <label>End</label>
                  <DateTimeField value={editForm.end_time} onChange={(e) => setEditForm({ ...editForm, end_time: e.target.value })} />
                </div>
              </div>
              <div className="field">
                <label>Requester name</label>
                <input value={editForm.requester_name} onChange={(e) => setEditForm({ ...editForm, requester_name: e.target.value })} />
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Congregation</label>
                  <input value={editForm.congregation} onChange={(e) => setEditForm({ ...editForm, congregation: e.target.value })} />
                </div>
                <div className="field">
                  <label>Headcount</label>
                  <input type="number" min="1" value={editForm.headcount} onChange={(e) => setEditForm({ ...editForm, headcount: e.target.value })} />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Email</label>
                  <input type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                </div>
                <div className="field">
                  <label>Phone</label>
                  <input value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
                </div>
              </div>
              <div className="field">
                <label>Purpose</label>
                <input value={editForm.purpose} onChange={(e) => setEditForm({ ...editForm, purpose: e.target.value })} />
              </div>
              <div className="field">
                <label>Notes</label>
                <textarea rows={2} value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} />
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <button type="button" className="btn btn-secondary" onClick={onCancelEdit}>Cancel</button>
                <button type="button" className="btn btn-primary" disabled={busyId === b.id} onClick={() => onSaveEdit(b.id)}>
                  Save changes
                </button>
              </div>
            </div>
          ) : (
            readOnly ? (
              <BookingRow
                key={b.id}
                booking={b}
                dim
                menu={[{ label: 'Delete…', destructive: true, disabled: busyId === b.id, onClick: () => onDeleteBooking(b.id) }]}
              />
            ) : b.status === 'pending' ? (
              <PendingRow
                key={b.id}
                booking={b}
                busy={busyId === b.id}
                onApprove={onApprove}
                onReject={onReject}
                menu={[
                  { label: 'Edit', onClick: () => onEdit(b) },
                  { label: 'Cancel booking…', onClick: () => onCancelBooking(b.id) },
                  { label: 'Delete…', destructive: true, onClick: () => onDeleteBooking(b.id) },
                ]}
              />
            ) : (
              <BookingRow
                key={b.id}
                booking={b}
                menu={[
                  { label: 'Edit', onClick: () => onEdit(b) },
                  b.status !== 'cancelled' && { label: 'Cancel booking…', onClick: () => onCancelBooking(b.id) },
                  { label: 'Delete…', destructive: true, onClick: () => onDeleteBooking(b.id) },
                ]}
              />
            )
          )
        )}
    </div>
  );
}
