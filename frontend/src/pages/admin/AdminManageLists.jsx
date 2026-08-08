import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

const RESOURCES = {
  congregations: {
    label: 'Congregations',
    singular: 'congregation',
    fieldLabel: 'Congregation / group name',
    list: (activeOnly) => api.listCongregations(activeOnly),
    create: (payload) => api.createCongregation(payload),
    update: (id, payload) => api.updateCongregation(id, payload),
    deactivate: (id) => api.deactivateCongregation(id),
  },
  purposes: {
    label: 'Booking purposes',
    singular: 'purpose',
    fieldLabel: 'Purpose name',
    list: (activeOnly) => api.listBookingPurposes(activeOnly),
    create: (payload) => api.createBookingPurpose(payload),
    update: (id, payload) => api.updateBookingPurpose(id, payload),
    deactivate: (id) => api.deactivateBookingPurpose(id),
  },
};

export default function AdminManageLists() {
  const [tab, setTab] = useState('congregations');

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Manage lists</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {Object.entries(RESOURCES).map(([key, r]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => setTab(key)}
          >
            {r.label}
          </button>
        ))}
      </div>
      <ListManager key={tab} resource={RESOURCES[tab]} />
    </div>
  );
}

function ListManager({ resource }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ name: '' });
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setItems(await resource.list(false));
  }

  useEffect(() => {
    load();
  }, [resource]);

  function startEdit(item) {
    setEditingId(item.id);
    setForm({ name: item.name });
  }

  function resetForm() {
    setEditingId(null);
    setForm({ name: '' });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      if (editingId) {
        await resource.update(editingId, form);
      } else {
        await resource.create(form);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeactivate(id) {
    if (!confirm(`Remove this ${resource.singular} from the list?`)) return;
    await resource.deactivate(id);
    await load();
  }

  async function handleReactivate(item) {
    await resource.update(item.id, { active: true });
    await load();
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 24, alignItems: 'start' }}>
      <form className="card" onSubmit={handleSubmit}>
        <h3 style={{ fontSize: 16, marginBottom: 14 }}>
          {editingId ? `Edit ${resource.singular}` : `Add a ${resource.singular}`}
        </h3>
        {error && <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>}
        <div className="field">
          <label>{resource.fieldLabel}</label>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {editingId && (
            <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
          )}
          <button className="btn btn-primary" style={{ flex: 1 }}>
            {editingId ? 'Save changes' : `Add ${resource.singular}`}
          </button>
        </div>
      </form>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((item) => (
          <div key={item.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>{item.name}</strong>
              {!item.active && <span className="badge badge-cancelled" style={{ marginLeft: 8 }}>Inactive</span>}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary" onClick={() => startEdit(item)}>Edit</button>
              {item.active ? (
                <button className="btn btn-danger" onClick={() => handleDeactivate(item.id)}>Remove</button>
              ) : (
                <button className="btn btn-secondary" onClick={() => handleReactivate(item)}>Restore</button>
              )}
            </div>
          </div>
        ))}
        {items.length === 0 && <p>No {resource.label.toLowerCase()} added yet.</p>}
      </div>
    </div>
  );
}
