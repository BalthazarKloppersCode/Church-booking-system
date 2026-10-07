import { format } from 'date-fns';
import { ALL_SLOTS, slotsWithValue } from '../../lib/timeSlots';
import DatePicker from './DatePicker';
import Select from './Select';

// Replaces <input type="datetime-local"> in the admin forms: a date picker next
// to a list of half-hour slots. Admin forms stay dense (§0), so the time is a
// compact dropdown of slots rather than the public flow's chip grid.
//
// value / onChange use the same 'YYYY-MM-DDTHH:mm' shape a native
// datetime-local input did.
export default function DateTimeField({ value, onChange, required }) {
  const [date = '', time = ''] = (value || '').split('T');
  const slots = slotsWithValue(ALL_SLOTS, time);

  function emit(nextDate, nextTime) {
    const d = nextDate || format(new Date(), 'yyyy-MM-dd');
    const t = nextTime || '09:00';
    onChange({ target: { value: `${d}T${t}` } });
  }

  return (
    <div style={{ display: 'flex', gap: 10 }}>
      <DatePicker
        size="admin"
        required={required}
        value={date}
        onChange={(e) => emit(e.target.value, time)}
        style={{ flex: '1 1 0', minWidth: 0 }}
      />
      <Select
        size="admin"
        required={required}
        value={time}
        placeholder="Time"
        aria-label="Time"
        onChange={(e) => emit(date, e.target.value)}
        style={{ flex: '0 0 110px' }}
      >
        {slots.map((slot) => (
          <option key={slot} value={slot}>{slot}</option>
        ))}
      </Select>
    </div>
  );
}
