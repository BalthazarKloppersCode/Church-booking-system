import { MULTI_ROOM_COLOR, NO_ROOM_COLOR } from '../lib/roomColors';

// The colour key under a calendar: each room, then the special looks.
export default function CalendarKey({ rooms, colors, showNoRoom = false }) {
  const ordered = [...rooms].sort((a, b) => a.name.localeCompare(b.name));
  return (
    <div className="cal-legend" aria-label="Calendar colour key">
      {ordered.map((room) => (
        <span key={room.id}>
          <span className="dot" style={{ background: colors.byId[room.id] }} />
          {room.name}
        </span>
      ))}
      <span>
        <span className="dot" style={{ background: MULTI_ROOM_COLOR }} />
        Several rooms
      </span>
      {showNoRoom && (
        <span>
          <span className="dot" style={{ background: NO_ROOM_COLOR }} />
          No room set
        </span>
      )}
      <span>
        <span
          className="dot"
          style={{ background: 'var(--wait-bg)', border: '1px dashed var(--wait)', width: 14, boxSizing: 'border-box' }}
        />
        Awaiting approval (the bar on the left is its room)
      </span>
    </div>
  );
}
