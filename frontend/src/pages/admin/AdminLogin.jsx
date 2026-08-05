import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../../lib/api';

export default function AdminLogin() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { access_token } = await api.adminLogin(form);
      localStorage.setItem('admin_token', access_token);
      navigate('/admin');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container" style={{ maxWidth: 400, paddingTop: 100 }}>
      <div className="eyebrow">
        <Link to="/" style={{ color: 'inherit' }}>← Back home</Link>
      </div>
      <h1 style={{ marginBottom: 24 }}>Admin login</h1>
      <form className="card" onSubmit={handleSubmit}>
        {error && <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>}
        <div className="field">
          <label>Email</label>
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </div>
        <button className="btn btn-primary btn-block" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p style={{ fontSize: 12, marginTop: 16, textAlign: 'center' }}>
        First time setting up? Create an admin account via the <code>/api/admin/register</code> endpoint —
        see README.
      </p>
    </div>
  );
}
