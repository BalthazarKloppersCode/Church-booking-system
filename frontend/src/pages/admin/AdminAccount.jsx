import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useAdmin } from '../../lib/useAdmin';
import Notice from '../../components/admin/Notice';

function checkNewPassword(password, confirm) {
  if (password.length < 8) return 'Choose a password of at least 8 characters.';
  if (password.length > 72) return 'Passwords can be at most 72 characters.';
  if (password !== confirm) return "The two new passwords don't match.";
  return '';
}

// Your own password, and — for when a colleague is locked out — a new password for another admin.
export default function AdminAccount() {
  const { admin } = useAdmin();
  const [admins, setAdmins] = useState(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    api.adminListAdmins().then(setAdmins).catch(() => setAdmins([]));
  }, []);

  return (
    <div style={{ maxWidth: 560 }}>
      <h1>My account</h1>
      {admin && <p style={{ margin: '0 0 20px', color: 'var(--ink-2)' }}>{admin.name} · {admin.email}</p>}
      {notice && <Notice onDismiss={() => setNotice('')}>{notice}</Notice>}

      <ChangeOwnPassword onChanged={() => setNotice('Your password has been changed.')} />

      <h2 style={{ fontSize: 18, margin: '32px 0 6px' }}>Other admins</h2>
      <p style={{ margin: '0 0 14px', fontSize: 14, color: 'var(--ink-2)' }}>
        If a colleague has forgotten their password, set a new one for them here and pass it on. They're signed out
        everywhere and can change it themselves afterwards.
      </p>
      {admins === null && <p>Loading…</p>}
      {admins && admins.filter((a) => a.id !== admin?.id).length === 0 && (
        <p style={{ fontSize: 14, color: 'var(--ink-3)' }}>There are no other admins.</p>
      )}
      <div style={{ display: 'grid', gap: 8 }}>
        {(admins || [])
          .filter((a) => a.id !== admin?.id)
          .map((a) => (
            <OtherAdmin key={a.id} other={a} onChanged={(name) => setNotice(`New password set for ${name}.`)} />
          ))}
      </div>
    </div>
  );
}

function ChangeOwnPassword({ onChanged }) {
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    const problem = checkNewPassword(form.next, form.confirm);
    if (problem) return setError(problem);
    setBusy(true);
    try {
      const result = await api.adminChangePassword(form.current, form.next);
      // Changing the password signs every old session out, including this one — keep going with the fresh token.
      localStorage.setItem('admin_token', result.access_token);
      setForm({ current: '', next: '', confirm: '' });
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2 style={{ fontSize: 18, margin: '0 0 12px' }}>Change my password</h2>
      {error && <p role="alert" style={{ color: 'var(--no)', fontSize: 13, margin: '0 0 10px' }}>{error}</p>}
      <div className="field">
        <label>Current password</label>
        <input type="password" required autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
      </div>
      <div className="field">
        <label>New password</label>
        <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
        <span className="field-hint">At least 8 characters.</span>
      </div>
      <div className="field">
        <label>Type the new password again</label>
        <input type="password" required autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
      </div>
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button>
    </form>
  );
}

function OtherAdmin({ other, onChanged }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ next: '', confirm: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    const problem = checkNewPassword(form.next, form.confirm);
    if (problem) return setError(problem);
    setBusy(true);
    try {
      await api.adminSetAdminPassword(other.id, form.next);
      setForm({ next: '', confirm: '' });
      setOpen(false);
      onChanged(other.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ padding: '12px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <strong>{other.name}</strong>
          <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>{other.email}</div>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => setOpen((o) => !o)}>
          {open ? 'Cancel' : 'Set new password'}
        </button>
      </div>
      {open && (
        <form onSubmit={submit} style={{ marginTop: 14 }}>
          {error && <p role="alert" style={{ color: 'var(--no)', fontSize: 13, margin: '0 0 10px' }}>{error}</p>}
          <div className="field-row">
            <div className="field">
              <label>New password</label>
              <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
            </div>
            <div className="field">
              <label>Type it again</label>
              <input type="password" required autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
            </div>
          </div>
          <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : `Set password for ${other.name}`}</button>
        </form>
      )}
    </div>
  );
}
