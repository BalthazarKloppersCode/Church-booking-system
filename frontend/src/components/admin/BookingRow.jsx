import { bookingBadge } from '../../lib/bookingStatus';
import { formatDayLong, formatRelative, formatSlot } from '../../lib/formatDate';
import OverflowMenu from './OverflowMenu';

// One scannable line per booking (DESIGN_DIRECTION.md §6 Booking row):
//
//   Main Hall  [Awaiting the office]
//   Wed 14 Oct · 10:00–12:00 · 2 hours
//   Erhard Louw · Brackenfell · 80 people · Training / workshop      [Approve] [···]
//
// One primary action (optional — a confirmed booking has none), everything
// else behind the overflow menu. `flat` drops the border so rows can sit inside
// a card without becoming cards-within-a-card (§5).
export default function BookingRow({ booking: b, primary, menu = [], meta, dim, flat, children }) {
  const badge = bookingBadge(b);
  const purpose = b.purpose_other ? `${b.purpose}: ${b.purpose_other}` : b.purpose;
  const who = [b.requester_name, b.congregation, b.is_private_event && 'Private event', `${b.headcount} people`, purpose]
    .filter(Boolean)
    .join(' · ');
  const requested = meta === undefined ? `Requested ${formatRelative(b.created_at)}` : meta;

  return (
    <div className="brow-wrap">
      <div className={`brow${dim ? ' is-dim' : ''}${flat ? ' is-flat' : ''}`}>
        <div className="brow-main">
          <div className="brow-top">
            <span className="brow-name">{b.room_name}</span>
            <span className={`badge badge-${badge.tone}`}>{badge.label}</span>
          </div>
          <div className="brow-when">{formatSlot(b.start_time, b.end_time)}</div>
          <div className="brow-who">{who}</div>
          {b.status === 'rejected' && b.admin_note && <div className="brow-reason">{b.admin_note}</div>}
        </div>
        {requested && (
          <span className="brow-meta" title={formatDayLong(b.created_at)}>{requested}</span>
        )}
        <div className="brow-actions">
          {primary && (
            <button type="button" className="btn btn-primary" style={{ height: 36, padding: '0 14px' }} disabled={primary.disabled} onClick={primary.onClick}>
              {primary.label}
            </button>
          )}
          <OverflowMenu items={menu} label={`More actions for ${b.room_name}`} />
        </div>
      </div>
      {children}
    </div>
  );
}
