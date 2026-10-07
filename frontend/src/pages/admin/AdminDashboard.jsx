import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api';
import AdminAnalyticsCharts from './AdminAnalyticsCharts';
import { formatDayLong } from '../../lib/formatDate';
import BookingRow from '../../components/admin/BookingRow';
import PendingRow from '../../components/admin/PendingRow';
import DatePicker from '../../components/fields/DatePicker';
import Select from '../../components/fields/Select';

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
  const [pending, setPending] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [allCongregations, setAllCongregations] = useState([]);
  const [allBookings, setAllBookings] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const [filterResults, setFilterResults] = useState(null);

  const [chartDays, setChartDays] = useState(30);
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);

  function reload() {
    return Promise.all([api.adminDashboard().then(setStats), api.adminApprovals().then(setPending)]);
  }

  useEffect(() => {
    reload();
    api.listCongregations(false).then(setAllCongregations);
  }, []);

  async function decide(id, action, note = null) {
    setBusyId(id);
    try {
      if (action === 'approve') await api.adminApprove(id, note);
      else await api.adminReject(id, note);
      await reload();
    } finally {
      setBusyId(null);
    }
  }

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
    setFilterOpen(false);
  }

  function clearFilter() {
    setFilter(EMPTY_FILTER);
    setFilterResults(null);
  }

  if (!stats || !pending) return <p>Loading…</p>;

  const WAITING_SHOWN = 8;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0 }}>Dashboard</h1>
          <div style={{ fontSize: 14, color: 'var(--ink-2)', marginTop: 3 }}>{formatDayLong(new Date())}</div>
        </div>
        <button className="btn btn-secondary" style={{ height: 36 }} onClick={() => setFilterOpen((open) => !open)}>
          {filterOpen ? 'Close filter' : 'Filter bookings'}
        </button>
      </div>

      {filterOpen && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 15, marginBottom: 14 }}>Filter bookings</h3>

          <div className="field">
            <label>Date range</label>
            <Select size="admin"
              value={filter.dateMode}
              onChange={(e) => setFilter({ ...filter, dateMode: e.target.value })}
            >
              <option value="">No date filter</option>
              <option value="after">After</option>
              <option value="before">Before</option>
              <option value="between">Between</option>
            </Select>
          </div>

          {(filter.dateMode === 'after' || filter.dateMode === 'between') && (
            <div className="field">
              <label>From</label>
              <DatePicker size="admin"
                value={filter.dateAfter}
                onChange={(e) => setFilter({ ...filter, dateAfter: e.target.value })}
              />
            </div>
          )}
          {(filter.dateMode === 'before' || filter.dateMode === 'between') && (
            <div className="field">
              <label>Until</label>
              <DatePicker size="admin"
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
                border: '1px solid var(--line)',
                borderRadius: 8,
                padding: 10,
              }}
            >
              {allCongregations.map((c) => (
                <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    style={{ minWidth: 160 }}
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
              <Select size="admin"
                value={filter.combinator}
                onChange={(e) => setFilter({ ...filter, combinator: e.target.value })}
              >
                <option value="AND">AND — must match both</option>
                <option value="OR">OR — match either</option>
              </Select>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-secondary" type="button" onClick={clearFilter}>Clear</button>
            <button className="btn btn-primary" type="button" onClick={applyFilter}>Apply filter</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: '17px 20px 8px', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
          <h3 style={{ margin: 0 }}>Waiting on you</h3>
          {pending.length > 0 && <span style={{ fontSize: 13, color: 'var(--ink-2)' }}>{pending.length} request{pending.length === 1 ? '' : 's'}</span>}
          <div style={{ flex: 1 }} />
          {pending.length > WAITING_SHOWN && (
            <Link to="/admin/bookings" style={{ fontSize: 13.5, fontWeight: 500 }}>See all</Link>
          )}
        </div>
        {pending.length === 0 ? (
          <p style={{ fontSize: 14, color: 'var(--ink-3)', padding: '10px 0 14px', margin: 0 }}>Nothing waiting on you.</p>
        ) : (
          <div>
            {pending.slice(0, WAITING_SHOWN).map((b) => (
              <PendingRow
                key={b.id}
                flat
                booking={b}
                busy={busyId === b.id}
                onApprove={(id) => decide(id, 'approve')}
                onReject={(id, note) => decide(id, 'reject', note)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="stat-strip" style={{ marginBottom: 16 }}>
        <div className="stat">
          <div className="stat-label">Bookings this week</div>
          <div className="stat-value">{stats.bookings_this_week}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Active rooms</div>
          <div className="stat-value">{stats.active_rooms}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Avg. approval time (30 days)</div>
          <div className="stat-value">
            {analyticsLoading ? '…' : analytics?.avg_approval_hours == null ? '—' : `${analytics.avg_approval_hours}h`}
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: '17px 20px 8px', marginBottom: 32 }}>
        {filterResults !== null ? (
          <>
            <h3 style={{ margin: '0 0 4px' }}>Filtered results ({filterResults.length})</h3>
            {filterResults.length === 0 && (
              <p style={{ fontSize: 14, color: 'var(--ink-3)', padding: '10px 0 14px', margin: 0 }}>No bookings match those filters.</p>
            )}
            {filterResults.map((b) => (
              <BookingRow key={b.id} flat booking={b} meta={null} />
            ))}
          </>
        ) : (
          <>
            <h3 style={{ margin: '0 0 4px' }}>Next confirmed bookings</h3>
            {stats.next_bookings.length === 0 && (
              <p style={{ fontSize: 14, color: 'var(--ink-3)', padding: '10px 0 14px', margin: 0 }}>Nothing confirmed yet.</p>
            )}
            {stats.next_bookings.map((b) => (
              <BookingRow key={b.id} flat booking={b} meta={null} />
            ))}
          </>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Analytics</h2>
        <Select size="admin"
          aria-label="Analytics period"
          value={chartDays}
          onChange={(e) => setChartDays(Number(e.target.value))}
          style={{ minWidth: 160 }}
        >
          {RANGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </Select>
      </div>
      <div style={{ marginBottom: 32 }}>
        {analyticsLoading && <p>Loading analytics…</p>}
        {!analyticsLoading && <AdminAnalyticsCharts data={analytics} />}
      </div>
    </div>
  );
}
