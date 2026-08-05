import { useEffect, useMemo, useState } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { api } from '../../lib/api';

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { locale: enUS }),
  getDay,
  locales: { 'en-US': enUS },
});

const STATUS_COLOR = {
  approved: '#1B3A6C',
  pending: '#C98A2C',
};

export default function AdminCalendar() {
  const [rooms, setRooms] = useState([]);
  const [roomFilter, setRoomFilter] = useState('');
  const [events, setEvents] = useState([]);

  useEffect(() => {
    api.listRooms().then(setRooms);
  }, []);

  useEffect(() => {
    api
      .listBookings(roomFilter ? { room_id: roomFilter } : {})
      .then((bookings) => {
        const filtered = bookings.filter((b) => b.status === 'approved' || b.status === 'pending');
        setEvents(
          filtered.map((b) => ({
            id: b.id,
            title: `${b.room_name} — ${b.congregation} (${b.headcount})`,
            start: new Date(b.start_time),
            end: new Date(b.end_time),
            status: b.status,
          }))
        );
      });
  }, [roomFilter]);

  const eventStyleGetter = useMemo(
    () => (event) => ({
      style: {
        backgroundColor: STATUS_COLOR[event.status] || '#5B6259',
        borderRadius: 6,
        border: 'none',
      },
    }),
    []
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1>Calendar</h1>
        <select
          value={roomFilter}
          onChange={(e) => setRoomFilter(e.target.value)}
          style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8 }}
        >
          <option value="">All rooms</option>
          {rooms.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
      </div>
      <div className="card" style={{ padding: 16 }}>
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: 650 }}
          eventPropGetter={eventStyleGetter}
        />
      </div>
    </div>
  );
}
