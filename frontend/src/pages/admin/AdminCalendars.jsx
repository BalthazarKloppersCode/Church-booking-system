import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import Notice from '../../components/admin/Notice';

// The Google calendars shown beside bookings. Each is added by pasting its private link; the link
// is a secret that stays on the server, so this page never shows it again, only where it points.
export default function AdminCalendars() {
  const [feeds, setFeeds] = useState(null);
  const [form, setForm] = useState({ name: '', url: '' });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmId, setConfirmId] = useState(null);

  async function load() {
    try {
      setFeeds(await api.adminListCalendarFeeds());
    } catch (err) {
      setError(err.message);
      setFeeds([]);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    setBusy(true);
    try {
      const made = await api.adminAddCalendarFeed(form.name.trim(), form.url.trim());
      setForm({ name: '', url: '' });
      setNotice(`${made.name} added. It has ${made.upcoming} event${made.upcoming === 1 ? '' : 's'} in the next 90 days and now shows on the calendars.`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(feed) {
    setError('');
    try {
      await api.adminUpdateCalendarFeed(feed.id, { enabled: !feed.enabled });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(feed) {
    setError('');
    try {
      await api.adminDeleteCalendarFeed(feed.id);
      setConfirmId(null);
      setNotice(`${feed.name} removed.`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <h1>Calendars</h1>
      <p style={{ margin: '0 0 18px' }}>
        Show events from your other Google calendars on the booking calendars, so everyone can see what is already on.
        Add each calendar with its private link. You can add as many as you need.
      </p>
      {notice && <Notice onDismiss={() => setNotice('')}>{notice}</Notice>}
      {error && <p role="alert" style={{ color: 'var(--no)', fontSize: 14 }}>{error}</p>}

      <div style={{ display: 'grid', gap: 10, marginBottom: 24 }}>
        {feeds === null && <p>Loading…</p>}
        {feeds && feeds.length === 0 && <p style={{ fontSize: 14, color: 'var(--ink-3)' }}>No calendars added yet.</p>}
        {(feeds || []).map((f) => (
          <div key={f.id ?? 'built-in'} className="card" style={{ padding: '14px 18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ minWidth: 0 }}>
                <strong style={{ fontSize: 15 }}>{f.name}</strong>
                {f.built_in && <span className="badge badge-cancelled" style={{ marginLeft: 8 }}>Main calendar</span>}
                {!f.enabled && <span className="badge badge-cancelled" style={{ marginLeft: 8 }}>Turned off</span>}
                <div style={{ fontSize: 13, color: 'var(--ink-3)', overflowWrap: 'anywhere' }}>{f.link_hint}</div>
                {f.enabled && (f.ok ? (
                  <div style={{ fontSize: 13, color: 'var(--ok)', marginTop: 4 }}>
                    Working. {f.upcoming} event{f.upcoming === 1 ? '' : 's'} in the next 90 days.
                  </div>
                ) : (
                  <div style={{ fontSize: 13, color: 'var(--no)', marginTop: 4 }}>Not working: {f.error}</div>
                ))}
              </div>
              {!f.built_in && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => toggle(f)}>{f.enabled ? 'Turn off' : 'Turn on'}</button>
                  {confirmId === f.id ? (
                    <>
                      <button type="button" className="btn btn-danger" onClick={() => remove(f)}>Yes, remove</button>
                      <button type="button" className="btn btn-ghost" onClick={() => setConfirmId(null)}>Keep it</button>
                    </>
                  ) : (
                    <button type="button" className="btn btn-danger" onClick={() => setConfirmId(f.id)}>Remove</button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <form className="card" onSubmit={add}>
        <h2 style={{ fontSize: 18, margin: '0 0 12px', fontFamily: 'var(--font-body)' }}>Add a calendar</h2>
        <div className="field">
          <label>Name people will see</label>
          <input required maxLength={80} placeholder="e.g. Youth, Kids, Cell groups" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <span className="field-hint">Shown after each event, for example “Youth night (Youth)”.</span>
        </div>
        <div className="field">
          <label>Private link (secret address in iCal format)</label>
          <input required placeholder="https://calendar.google.com/calendar/ical/…/basic.ics" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Checking the link…' : 'Add calendar'}</button>
      </form>

      <div className="card" style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 18, margin: '0 0 8px', fontFamily: 'var(--font-body)' }}>Where do I find the link?</h2>
        <ol style={{ margin: '0 0 10px', paddingLeft: 20, fontSize: 14, lineHeight: 1.6, color: 'var(--ink)' }}>
          <li>On a computer, open <strong>calendar.google.com</strong> and sign in with the account that owns the calendar.</li>
          <li>Click the <strong>⚙ gear</strong>, then <strong>Settings</strong>.</li>
          <li>On the left, under “Settings for my calendars”, click the calendar you want.</li>
          <li>Scroll to <strong>Integrate calendar</strong> and copy <strong>Secret address in iCal format</strong>.</li>
          <li>Paste it above with a name. Do each calendar separately: every one has its own link.</li>
        </ol>
        <p style={{ fontSize: 13, margin: 0 }}>
          If the secret address isn't there, you're not the owner of that calendar. Ask whoever owns it.
          Anyone holding a link can read the whole calendar, so don't share it. Events marked Private in Google are never shown here.
        </p>
      </div>
    </div>
  );
}
