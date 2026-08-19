import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

const EMPTY_USER = { name: '', email: '', phone: '', area_id: '', password: '' };

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [areas, setAreas] = useState([]);
  const [form, setForm] = useState(EMPTY_USER);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setUsers(await api.listUsers());
  }

  useEffect(() => {
    load();
    api.listAreas(false).then(setAreas);
  }, []);

  function areaName(areaId) {
    return areas.find((a) => a.id === areaId)?.name || 'No area set';
  }

  function startEdit(user) {
    setEditingId(user.id);
    setForm({ name: user.name, email: user.email, phone: user.phone, area_id: user.area_id || '', password: '' });
  }

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_USER);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = { name: form.name, email: form.email, phone: form.phone, area_id: form.area_id || null };
      if (editingId) {
        if (form.password) payload.password = form.password;
        await api.updateUser(editingId, payload);
      } else {
        payload.password = form.password;
        await api.createUser(payload);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this user? They will no longer be able to log in.')) return;
    await api.deleteUser(id);
    await load();
  }

  return (
    <div>
      <h1 style={{ marginBottom: 6 }}>Manage users</h1>
      <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 24 }}>
        Registered users who can log in to book for areas that require login (e.g. Northern Hub).
        A booking's contact details can still be for someone else — the login just proves who's allowed to submit it.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 24, alignItems: 'start' }}>
        <form className="card" onSubmit={handleSubmit}>
          <h3 style={{ fontSize: 16, marginBottom: 14 }}>
            {editingId ? 'Edit user' : 'Add a user'}
          </h3>
          {error && <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>}
          <div className="field">
            <label>Name</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field">
            <label>Email</label>
            <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field">
            <label>Phone</label>
            <input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="field">
            <label>Area</label>
            <select
              value={form.area_id}
              onChange={(e) => setForm({ ...form, area_id: e.target.value })}
            >
              <option value="">No area (always needs approval)</option>
              {areas.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
            <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 4 }}>
              Drives whether this person's bookings get the 2-week auto-approve window —
              set it to the area they belong to (e.g. Northern Hub), not their congregation.
            </p>
          </div>
          <div className="field">
            <label>{editingId ? 'New password (leave blank to keep current)' : 'Password'}</label>
            <input
              type="password"
              required={!editingId}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {editingId && (
              <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
            )}
            <button className="btn btn-primary" style={{ flex: 1 }}>
              {editingId ? 'Save changes' : 'Add user'}
            </button>
          </div>
        </form>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {users.map((u) => (
            <div key={u.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong>{u.name}</strong>
                {!u.active && <span className="badge badge-cancelled" style={{ marginLeft: 8 }}>Inactive</span>}
                <p style={{ fontSize: 13 }}>{u.email} · {u.phone}</p>
                <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{areaName(u.area_id)}</p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => startEdit(u)}>Edit</button>
                <button className="btn btn-danger" onClick={() => handleDelete(u.id)}>Delete</button>
              </div>
            </div>
          ))}
          {users.length === 0 && <p>No users added yet.</p>}
        </div>
      </div>
    </div>
  );
}
