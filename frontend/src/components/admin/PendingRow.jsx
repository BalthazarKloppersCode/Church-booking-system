import { useState } from 'react';
import BookingRow from './BookingRow';

// A booking awaiting the office's decision: Approve is the one primary action;
// declining is quiet, behind the menu, and asks for a reason first — the
// reason goes to the requester, which is what turns a "no" into a next step.
export default function PendingRow({ booking, busy, onApprove, onReject, menu = [], flat }) {
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');

  return (
    <BookingRow
      booking={booking}
      flat={flat}
      primary={{ label: 'Approve', disabled: busy, onClick: () => onApprove(booking.id) }}
      menu={[{ label: 'Decline…', onClick: () => setDeclining(true) }, ...menu]}
    >
      {declining && (
        <div
          style={{
            marginTop: 8,
            padding: 14,
            background: flat ? 'var(--stone)' : 'var(--paper)',
            border: flat ? 'none' : '1px solid var(--line)',
            borderRadius: flat ? 8 : 12,
          }}
        >
          <div className="field" style={{ marginBottom: 12 }}>
            <label>Reason for declining (sent to the requester)</label>
            <input
              autoFocus
              placeholder="e.g. Clashes with Youth — LEAP 2 is free that evening"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-ghost" onClick={() => setDeclining(false)}>Keep it</button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={busy}
              onClick={() => onReject(booking.id, reason.trim() || null)}
            >
              Decline booking
            </button>
          </div>
        </div>
      )}
    </BookingRow>
  );
}
