import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api';
import AdminAnalyticsCharts from './AdminAnalyticsCharts';

const EMPTY_FILTER = {
  dateMode: '', // '', 'after', 'before', 'between'
  dateAfter: '',
  dateBefore: '',
  congregations: [], // selected congregation names
  combinator: 'AND',
};

const RANGE_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [allCongregations, setAllCongregations] = useState([]);
  const [allBookings, setAllBookings] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const [filterResults, setFilterResults] = useState(null);

  const [chartDays, setChartDays] = useState(30);
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);

  useEffect(() => {
    api.adminDashboard().then(setStats);
    api.listCongregations(false).then(setAllCongregations);
  }, []);

  useEffect(() => {
    setAnalyticsLoading(true);
    api
      .adminAnalytics(chartDays)
      .then(setAnalytics)
      .finally(() => setAnalyticsLoading(false));
  }, [chartDays]);

  function toggleCongregation(name) {
    setFilter((f) => ({
      ...f,
      congregations: f.congregations.includes(name)
        ? f.congregations.filter((n) => n !== name)
        : [...f.congregations, name],
    }));
  }

  async function applyFilter() {
    let bookings = allBookings;
    if (!bookings) {
      bookings = await api.listBookings({});
      setAllBookings(bookings);
    }

    const dateActive = !!filter.dateMode;
    const congActive = filter.congregations.length > 0;

    const matchesDate = (b) => {
      const t = new Date(b.start_time);
      if (filter.dateMode === 'after') return !filter.dateAfter || t >= new Date(filter.dateAfter);
      if (filter.dateMode === 'before') return !filter.dateBefore || t <= new Date(filter.dateBefore);
      if (filter.dateMode === 'between') {
        return (
          (!filter.dateAfter || t >= new Date(filter.dateAfter)) &&
          (!filter.dateBefore || t <= new Date(filter.dateBefore))
        );
      }
      return true;
    };
    const matchesCongregation = (b) => filter.congregations.includes(b.congregation);

    const results = bookings.filter((b) => {
      if (dateActive && congActive) {
        return filter.combinator === 'AND'
          ? matchesDate(b) && matchesCongregation(b)
          : matchesDate(b) || matchesCongregation(b);
      }
      if (dateActive) return matchesDate(b);
      if (congActive) return matchesCongregation(b);
      return true;
    });

    results.sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
    setFilterResults(results);
  }

  function clearFilter() {
    setFilter(EMPTY_FILTER);
    setFilterResults(null);
  }

  if (!stats) return <p>Loading…</p>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1>Dashboard</h1>
        <button className="btn btn-secondary" onClick={() => setFilterOpen((open) => !open)}>
          {filterOpen ? 'Close filter' : 'Filter bookings'}
        </button>
      </div>

      {filterOpen && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 15, marginBottom: 14 }}>Filter bookings</h3>

          <div className="field">
            <label>Date range</label>
            <select
              value={filter.dateMode}
              onChange={(e) => setFilter({ ...filter, dateMode: e.target.value })}
            >
              <option value="">No date filter</option>
              <option value="after">After</option>
              <option value="before">Before</option>
              <option value="between">Between</option>
            </select>
          </div>

          {(filter.dateMode === 'after' || filter.dateMode === 'between') && (
            <div className="field">
              <label>From</label>
              <input
                type="date"
                value={filter.dateAfter}
                onChange={(e) => setFilter({ ...filter, dateAfter: e.target.value })}
              />
            </div>
          )}
          {(filter.dateMode === 'before' || filter.dateMode === 'between') && (
            <div className="field">
              <label>Until</label>
              <input
                type="date"
                value={filter.dateBefore}
                onChange={(e) => setFilter({ ...filter, dateBefore: e.target.value })}
              />
            </div>
          )}

          <div className="field">
            <label>Congregations (select one or more)</label>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                maxHeight: 180,
                overflowY: 'auto',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 10,
              }}
            >
              {allCongregations.map((c) => (
                <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    style={{ width: 'auto' }}
                    checked={filter.congregations.includes(c.name)}
                    onChange={() => toggleCongregation(c.name)}
                  />
                  {c.name}
                </label>
              ))}
              {allCongregations.length === 0 && (
                <p style={{ fontSize: 13, margin: 0 }}>No congregations set up yet.</p>
              )}
            </div>
          </div>

          {!!filter.dateMode && filter.congregations.length > 0 && (
            <div className="field">
              <label>Combine date range and congregations with</label>
              <select
                value={filter.combinator}
                onChange={(e) => setFilter({ ...filter, combinator: e.target.value })}
              >
                <option value="AND">AND — must match both</option>
                <option value="OR">OR — match either</option>
              </select>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-secondary" type="button" onClick={clearFilter}>Clear</button>
            <button className="btn btn-primary" type="button" onClick={applyFilter}>Apply filter</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard
          label="Awaiting approval"
          value={stats.pending_approvals}
          accent="var(--amber)"
          link={stats.pending_approvals > 0 ? '/admin/approvals' : null}
        />
        <StatCard label="Bookings this week" value={stats.bookings_this_week} accent="var(--teal)" />
        <StatCard label="Active rooms" value={stats.active_rooms} accent="var(--success)" />
        <StatCard
          label="Avg. approval time (30d)"
          value={
            analyticsLoading
              ? '…'
              : analytics?.avg_approval_hours == null
                ? '—'
                : `${analytics.avg_approval_hours}h`
          }
          accent="var(--teal)"
        />
      </div>

      <Link to="/admin/congregations/dashboard" style={{ display: 'inline-block', marginBottom: 28, fontSize: 14 }}>
        View bookings by congregation →
      </Link>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ fontSize: 18 }}>Analytics</h2>
        <select
          value={chartDays}
          onChange={(e) => setChartDays(Number(e.target.value))}
          style={{ width: 'auto' }}
        >
          {RANGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
      <div style={{ marginBottom: 32 }}>
        {analyticsLoading && <p>Loading analytics…</p>}
        {!analyticsLoading && <AdminAnalyticsCharts data={analytics} />}
      </div>

      {filterResults !== null ? (
        <>
          <h2 style={{ fontSize: 18, marginBottom: 14 }}>Filtered results ({filterResults.length})</h2>
          {filterResults.length === 0 && <p>No bookings match those filters.</p>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filterResults.map((b) => (
              <div key={b.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{b.room_name}</strong> — {b.congregation}
                  <p style={{ fontSize: 13 }}>
                    {new Date(b.start_time).toLocaleString()} · {b.headcount} people · {b.purpose}
                  </p>
                </div>
                <span className={`badge badge-${b.status}`}>{b.status}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <h2 style={{ fontSize: 18, marginBottom: 14 }}>Next confirmed bookings</h2>
          {stats.next_bookings.length === 0 && <p>Nothing confirmed yet.</p>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {stats.next_bookings.map((b) => (
              <div key={b.id} className="card" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <strong>{b.room_name}</strong> — {b.congregation}
                  <p style={{ fontSize: 13 }}>{new Date(b.start_time).toLocaleString()}</p>
                </div>
                <span className="badge badge-approved">{b.headcount} people</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, accent, link }) {
  const content = (
    <div className="card">
      <div style={{ fontSize: 34, fontFamily: 'var(--font-display)', color: accent }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{label}</div>
    </div>
  );
  return link ? <Link to={link} style={{ textDecoration: 'none' }}>{content}</Link> : content;
}
