import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut, Bar, Line } from 'react-chartjs-2';
import { formatDateRange } from '../../lib/formatDate';

function weekLabel(weekStartIso) {
  const start = new Date(`${weekStartIso}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return formatDateRange(start, end);
}

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend
);

const CHART_COLORS = [
  '#1B3A6C', '#1B5FAE', '#C98A2C', '#3F7A5C', '#B5453A',
  '#6B8CAE', '#8CA88F', '#D9A441', '#7A5A9E', '#4C9C9C',
];

function colorFor(index) {
  return CHART_COLORS[index % CHART_COLORS.length];
}

function ChartCard({ title, children }) {
  return (
    <div className="card">
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>{title}</h3>
      {children}
    </div>
  );
}

function DonutChart({ rows }) {
  return (
    <Doughnut
      data={{
        labels: rows.map((r) => r.label),
        datasets: [{ data: rows.map((r) => r.count), backgroundColor: rows.map((_, i) => colorFor(i)) }],
      }}
      options={{
        responsive: true,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
      }}
    />
  );
}

// Render only the charts that have something to chart; if none do, say so once
// (DESIGN_DIRECTION.md §8) instead of four cards that each say "No data".
export default function AdminAnalyticsCharts({ data }) {
  if (!data) return null;

  const hasCongregations = data.by_congregation.length > 0;
  const hasPurposes = data.by_purpose.length > 0;
  const hasRooms = data.by_room.length > 0;
  const hasWeekly = data.weekly.length > 0;

  if (!hasCongregations && !hasPurposes && !hasRooms && !hasWeekly) {
    return <p style={{ fontSize: 14, color: 'var(--ink-3)', margin: 0 }}>No bookings in this period.</p>;
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
      {hasCongregations && (
        <ChartCard title="Bookings by congregation">
          <DonutChart rows={data.by_congregation} />
        </ChartCard>
      )}

      {hasPurposes && (
        <ChartCard title="Bookings by purpose">
          <DonutChart rows={data.by_purpose} />
        </ChartCard>
      )}

      {hasRooms && (
        <ChartCard title="Room utilization">
          <Bar
            data={{
              labels: data.by_room.map((r) => r.label),
              datasets: [{ label: 'Bookings', data: data.by_room.map((r) => r.count), backgroundColor: '#1B3A6C' }],
            }}
            options={{
              responsive: true,
              plugins: { legend: { display: false } },
              scales: { y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0 } } },
            }}
          />
        </ChartCard>
      )}

      {hasWeekly && (
        <ChartCard title="Bookings over time (weekly)">
          <Line
            data={{
              labels: data.weekly.map((w) => weekLabel(w.week_start)),
              datasets: [
                {
                  label: 'Bookings',
                  data: data.weekly.map((w) => w.count),
                  borderColor: '#1B3A6C',
                  backgroundColor: '#1B3A6C',
                  tension: 0.3,
                },
              ],
            }}
            options={{
              responsive: true,
              plugins: { legend: { display: false } },
              scales: { y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0 } } },
            }}
          />
        </ChartCard>
      )}
    </div>
  );
}
