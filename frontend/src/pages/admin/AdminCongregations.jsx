import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

const EMPTY_CONGREGATION = { name: '' };

export default function AdminCongregations() {
  const [congregations, setCongregations] = useState([]);
  const [form, setForm] = useState(EMPTY_CONGREGATION);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setCongregations(await api.listCongregations(false));
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit(congregation) {
    setEditingId(congregation.id);
    setForm({ name: congregation.name });
  }

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_CONGREGATION);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      if (editingId) {
        await api.updateCongregation(editingId, form);
      } else {
        await api.createCongregation(form);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeactivate(id) {
    if (!confirm('Remove this congregation from the booking list?')) return;
    await api.deactivateCongregation(id);
    await load();
  }

  async function handleReactivate(congregation) {
    await api.updateCongregation(congregation.id, { active: true });
    await load();
  }

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Manage congregations</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 24, alignItems: 'start' }}>
        <form className="card" onSubmit={handleSubmit}>
          <h3 style={{ fontSize: 16, marginBottom: 14 }}>
            {editingId ? 'Edit congregation' : 'Add a congregation'}
          </h3>
          {error && <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>}
          <div className="field">
            <label>Congregation / group name</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {editingId && (
              <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
            )}
            <button className="btn btn-primary" style={{ flex: 1 }}>
              {editingId ? 'Save changes' : 'Add congregation'}
            </button>
          </div>
        </form>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {congregations.map((c) => (
            <div key={c.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong>{c.name}</strong>
                {!c.active && <span className="badge badge-cancelled" style={{ marginLeft: 8 }}>Inactive</span>}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => startEdit(c)}>Edit</button>
                {c.active ? (
                  <button className="btn btn-danger" onClick={() => handleDeactivate(c.id)}>Remove</button>
                ) : (
                  <button className="btn btn-secondary" onClick={() => handleReactivate(c)}>Restore</button>
                )}
              </div>
            </div>
          ))}
          {congregations.length === 0 && <p>No congregations added yet.</p>}
        </div>
      </div>
    </div>
  );
}
