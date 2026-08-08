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

function EmptyNote() {
  return <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No data for this period.</p>;
}

function DonutChart({ rows }) {
  if (!rows || rows.length === 0) return <EmptyNote />;
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

export default function AdminAnalyticsCharts({ data }) {
  if (!data) return null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
      <ChartCard title="Bookings by congregation">
        <DonutChart rows={data.by_congregation} />
      </ChartCard>

      <ChartCard title="Bookings by purpose">
        <DonutChart rows={data.by_purpose} />
      </ChartCard>

      <ChartCard title="Room utilization">
        {data.by_room.length === 0 ? (
          <EmptyNote />
        ) : (
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
        )}
      </ChartCard>

      <ChartCard title="Bookings over time (weekly)">
        {data.weekly.length === 0 ? (
          <EmptyNote />
        ) : (
          <Line
            data={{
              labels: data.weekly.map((w) => w.week_start),
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
        )}
      </ChartCard>
    </div>
  );
}
