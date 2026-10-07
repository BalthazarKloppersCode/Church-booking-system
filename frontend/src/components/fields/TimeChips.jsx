import { useState } from 'react';
import { ALL_SLOTS, DEFAULT_SLOTS, isDefaultSlot, slotsWithValue, toMinutes } from '../../lib/timeSlots';

// Time as a list of half-hour slots (DESIGN_DIRECTION.md §6 Fields) in place of
// <input type="time">. Shows 06:00–21:30 by default with the rest of the day
// behind "Show all hours", mirroring the calendar's collapsed window.
//
// onChange receives { target: { value } } so call sites read like a native input.
export default function TimeChips({ value, onChange, after, 'aria-label': ariaLabel }) {
  const [expandedByUser, setExpandedByUser] = useState(false);
  // A value outside the default window (picked from the calendar, say) must be
  // visible, so it forces the full day open.
  const expanded = expandedByUser || (!!value && !isDefaultSlot(value));
  const slots = slotsWithValue(expanded ? ALL_SLOTS : DEFAULT_SLOTS, value);
  const afterMinutes = after ? toMinutes(after) : null;

  return (
    <div>
      <div className="time-chips" role="radiogroup" aria-label={ariaLabel}>
        {slots.map((slot) => {
          const disabled = afterMinutes !== null && toMinutes(slot) <= afterMinutes;
          return (
            <button
              key={slot}
              type="button"
              role="radio"
              aria-checked={slot === value}
              disabled={disabled}
              className={`time-chip${slot === value ? ' is-on' : ''}`}
              onClick={() => onChange({ target: { value: slot } })}
            >
              {slot}
            </button>
          );
        })}
      </div>
      <button
        type="button"
        className="time-chips-toggle"
        onClick={() => setExpandedByUser((e) => !e)}
        disabled={!!value && !isDefaultSlot(value)}
      >
        {expanded ? 'Show fewer hours' : 'Show all hours'}
      </button>
    </div>
  );
}
