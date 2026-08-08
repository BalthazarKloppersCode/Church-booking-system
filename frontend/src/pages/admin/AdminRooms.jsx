import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

const EMPTY_ROOM = {
  name: '',
  type: 'classroom',
  capacity: '',
  location: '',
  description: '',
  setup_notes: '',
};

export default function AdminRooms() {
  const [rooms, setRooms] = useState([]);
  const [form, setForm] = useState(EMPTY_ROOM);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setRooms(await api.listRooms());
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit(room) {
    setEditingId(room.id);
    setForm({
      name: room.name,
      type: room.type,
      capacity: room.capacity,
      location: room.location || '',
      description: room.description || '',
      setup_notes: room.setup_notes || '',
    });
  }

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_ROOM);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = { ...form, capacity: Number(form.capacity) };
      if (editingId) {
        await api.updateRoom(editingId, payload);
      } else {
        await api.createRoom(payload);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeactivate(id) {
    if (!confirm('Remove this room from the booking list?')) return;
    await api.deactivateRoom(id);
    await load();
  }

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Manage rooms</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 24, alignItems: 'start' }}>
        <form className="card" onSubmit={handleSubmit}>
          <h3 style={{ fontSize: 16, marginBottom: 14 }}>
            {editingId ? 'Edit room' : 'Add a room'}
          </h3>
          {error && <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>}
          <div className="field">
            <label>Room name</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field">
            <label>Type</label>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="classroom">Classroom</option>
              <option value="training_hall">Training hall</option>
              <option value="main_hall">Main hall</option>
              <option value="coffee_shop">Coffee shop</option>
              <option value="lounge">Lounge</option>
              <option value="leap">Leap</option>
            </select>
          </div>
          <div className="field">
            <label>Capacity</label>
            <input
              type="number"
              min="1"
              required
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Location (optional)</label>
            <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </div>
          <div className="field">
            <label>What's in the room (furniture, equipment, what the booker should bring)</label>
            <textarea
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Setup instructions (what it should look like when done)</label>
            <textarea
              rows={3}
              value={form.setup_notes}
              onChange={(e) => setForm({ ...form, setup_notes: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {editingId && (
              <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
            )}
            <button className="btn btn-primary" style={{ flex: 1 }}>
              {editingId ? 'Save changes' : 'Add room'}
            </button>
          </div>
        </form>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {rooms.map((room) => (
            <div key={room.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong>{room.name}</strong>
                <p style={{ fontSize: 13 }}>
                  {room.type.replace('_', ' ')} · Capacity {room.capacity}
                  {room.location ? ` · ${room.location}` : ''}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => startEdit(room)}>Edit</button>
                <button className="btn btn-danger" onClick={() => handleDeactivate(room.id)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
