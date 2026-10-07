import { useState } from 'react';
import { DAY_LAST_MINUTE, fromMinutes, toMinutes } from '../../lib/timeSlots';
import TimeChips from './TimeChips';

const DURATIONS = [
  { minutes: 60, label: '1 hr' },
  { minutes: 90, label: '1½ hrs' },
  { minutes: 120, label: '2 hrs' },
  { minutes: 180, label: '3 hrs' },
];

// "How long?" is a question people can answer; "end time" makes them do
// arithmetic (DESIGN_DIRECTION.md mockup, screen 2). "Custom" falls back to
// picking an end slot so nothing the old free end-time input allowed is lost.
//
// onChange receives { target: { value } } with the new end time ('HH:mm').
export default function DurationChips({ start, end, onChange }) {
  const duration = toMinutes(end) - toMinutes(start);
  const matchesPreset = DURATIONS.some((d) => d.minutes === duration);
  const [customOpen, setCustomOpen] = useState(!matchesPreset);
  const custom = customOpen || !matchesPreset;

  return (
    <div>
      <div className="time-chips" role="radiogroup" aria-label="How long?">
        {DURATIONS.map((d) => {
          const tooLate = toMinutes(start) + d.minutes > DAY_LAST_MINUTE;
          const on = !custom && d.minutes === duration;
          return (
            <button
              key={d.minutes}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={tooLate}
              className={`time-chip${on ? ' is-on' : ''}`}
              onClick={() => {
                setCustomOpen(false);
                onChange({ target: { value: fromMinutes(toMinutes(start) + d.minutes) } });
              }}
            >
              {d.label}
            </button>
          );
        })}
        <button
          type="button"
          role="radio"
          aria-checked={custom}
          className={`time-chip${custom ? ' is-on' : ''}`}
          onClick={() => setCustomOpen(true)}
        >
          Custom
        </button>
      </div>
      {custom && (
        <div style={{ marginTop: 12 }}>
          <div className="field-sublabel">Ends at</div>
          <TimeChips value={end} after={start} onChange={onChange} aria-label="End time" />
        </div>
      )}
      <div className="field-hint">Ends at {end}</div>
    </div>
  );
}
