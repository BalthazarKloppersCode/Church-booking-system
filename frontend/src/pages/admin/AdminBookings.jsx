import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

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
      <label style={{ fontSize: 13, color: 'var(--ink-soft)' }}>Sort by</label>
      <select
        value={sortKey}
        onChange={(e) => setSortKey(e.target.value)}
        style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 8 }}
      >
        {SORT_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
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
  const [notes, setNotes] = useState({});
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

  async function decide(id, action) {
    setBusyId(id);
    try {
      if (action === 'approve') await api.adminApprove(id, notes[id] || null);
      else await api.adminReject(id, notes[id] || null);
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
      <h1 style={{ marginBottom: 20 }}>Bookings</h1>
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
          emptyText="No active bookings."
        />
      )}

      {tab === 'approvals' && (
        <ApprovalsTab
          bookings={pending ? sortBookings(pending, sortKey, sortDir) : null}
          notes={notes}
          setNotes={setNotes}
          busyId={busyId}
          onDecide={decide}
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
    </div>
  );
}

function ApprovalsTab({ bookings, notes, setNotes, busyId, onDecide }) {
  if (!bookings) return <p>Loading…</p>;
  return (
    <div>
      <p style={{ marginBottom: 20 }}>
        Bookings more than two weeks out, marked as private events, or from areas that always
        need approval, wait here for a decision.
      </p>
      {bookings.length === 0 && <p>Nothing waiting on you right now.</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {bookings.map((b) => (
          <div key={b.id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <div>
                <h3 style={{ fontSize: 17 }}>{b.room_name}</h3>
                <p style={{ fontSize: 13 }}>
                  {new Date(b.start_time).toLocaleString()} – {new Date(b.end_time).toLocaleTimeString()}
                </p>
              </div>
              {b.is_private_event && <span className="badge badge-pending">Private event</span>}
            </div>
            <p style={{ fontSize: 14 }}>
              <strong>{b.requester_name}</strong> ({b.congregation}) · {b.headcount} people
            </p>
            <p style={{ fontSize: 14 }}>{b.purpose}</p>
            {b.notes && <p style={{ fontSize: 13, fontStyle: 'italic' }}>Note: {b.notes}</p>}
            <p style={{ fontSize: 12 }}>{b.email} · {b.phone}</p>
            <p style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Booked {new Date(b.created_at).toLocaleString()}</p>

            <input
              placeholder="Optional note to include in the response"
              value={notes[b.id] || ''}
              onChange={(e) => setNotes({ ...notes, [b.id]: e.target.value })}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 8, margin: '10px 0' }}
            />

            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" disabled={busyId === b.id} onClick={() => onDecide(b.id, 'approve')}>
                Approve
              </button>
              <button className="btn btn-danger" disabled={busyId === b.id} onClick={() => onDecide(b.id, 'reject')}>
                Reject
              </button>
            </div>
          </div>
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
  readOnly,
  emptyText,
}) {
  if (!bookingsLoaded) return <p>Loading…</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {bookings.length === 0 && <p>{emptyText}</p>}
      {bookings.map((b) =>
          editingId === b.id ? (
            <div key={b.id} className="card">
              {error && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 10 }}>{error}</p>}
              <div className="field-row">
                <div className="field">
                  <label>Room</label>
                  <select value={editForm.room_id} onChange={(e) => setEditForm({ ...editForm, room_id: e.target.value })}>
                    {rooms.map((r) => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Status</label>
                  <select value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
                    <option value="pending">Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Start</label>
                  <input type="datetime-local" value={editForm.start_time} onChange={(e) => setEditForm({ ...editForm, start_time: e.target.value })} />
                </div>
                <div className="field">
                  <label>End</label>
                  <input type="datetime-local" value={editForm.end_time} onChange={(e) => setEditForm({ ...editForm, end_time: e.target.value })} />
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
            <div key={b.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <h3 style={{ fontSize: 16 }}>{b.room_name}</h3>
                  <span className={`badge badge-${b.status}`}>{b.status}</span>
                </div>
                <p style={{ fontSize: 13 }}>
                  {new Date(b.start_time).toLocaleString()} – {new Date(b.end_time).toLocaleTimeString()}
                </p>
                <p style={{ fontSize: 13 }}>
                  {b.requester_name} ({b.congregation}) · {b.headcount} people · {b.purpose}
                </p>
                <p style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Booked {new Date(b.created_at).toLocaleString()}</p>
              </div>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                {!readOnly && b.status === 'pending' && (
                  <button className="btn btn-primary" disabled={busyId === b.id} onClick={() => onApprove(b.id)}>
                    Approve
                  </button>
                )}
                {!readOnly && (
                  <button className="btn btn-secondary" disabled={busyId === b.id} onClick={() => onEdit(b)}>
                    Edit
                  </button>
                )}
                {!readOnly && b.status !== 'cancelled' && (
                  <button className="btn btn-secondary" disabled={busyId === b.id} onClick={() => onCancelBooking(b.id)}>
                    Cancel
                  </button>
                )}
                <button className="btn btn-danger" disabled={busyId === b.id} onClick={() => onDeleteBooking(b.id)}>
                  Delete
                </button>
              </div>
            </div>
          )
        )}
    </div>
  );
}
