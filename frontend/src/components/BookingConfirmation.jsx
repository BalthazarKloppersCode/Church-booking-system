import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { bookingBadge } from '../lib/bookingStatus';
import { formatSlot } from '../lib/formatDate';
import { buildIcs, downloadFile } from '../lib/ics';

// The confirmation email, on screen — so a booker has something to keep even
// when an email never arrives. Rendered from the same content the email is
// built from (GET /api/bookings/{id}/confirmation), so the two can't drift.
// Save as PDF uses the browser's own print dialog; Add to calendar downloads
// an .ics file; Copy puts the details on the clipboard as plain text.

function plainText(c, status) {
  const lines = [c.brand, '', `Dear ${c.recipient_name},`, '', c.intro, '', 'BOOKING DETAILS'];
  c.details.forEach((d) => lines.push(`${d.label}: ${d.value}`));
  if (c.room_notes.setup_notes) lines.push('', `When you're done, please leave the room like this: ${c.room_notes.setup_notes}`);
  if (c.room_notes.booking_message) lines.push('', c.room_notes.booking_message);
  lines.push('', c.reminders_heading.toUpperCase());
  c.reminders.forEach((r) => lines.push(`- ${r}`));
  c.extra_notes.forEach((n) => lines.push('', n));
  lines.push('', c.access_note);
  if (c.cancellation) lines.push('', c.cancellation);
  c.closing.forEach((n) => lines.push('', n));
  lines.push('', 'Kind regards,', c.sign_off);
  if (status === 'pending') lines.unshift('REQUEST ONLY — not yet confirmed by the office.', '');
  return lines.join('\n');
}

export default function BookingConfirmation({ bookingId, email }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getBookingConfirmation(bookingId, email)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [bookingId, email]);

  if (error) return <p style={{ color: 'var(--no)', fontSize: 13 }}>Couldn't load the confirmation: {error}</p>;
  if (!data) return <p style={{ fontSize: 13, color: 'var(--ink-3)' }}>Loading your confirmation…</p>;

  const { content: c, status } = data;
  const badge = bookingBadge({ status, end_time: data.end_time });
  const details = Object.fromEntries(c.details.map((d) => [d.label, d.value]));

  function savePdf() {
    // The print dialog names the PDF after the page title.
    const original = document.title;
    document.title = `Booking - ${c.event}`;
    window.addEventListener('afterprint', () => { document.title = original; }, { once: true });
    window.print();
  }

  function addToCalendar() {
    const location = [data.room_name, details.Location].filter(Boolean).join(', ');
    const description = [c.reference && `Reference: ${c.reference}`, details['Room equipment'] && `Room equipment: ${details['Room equipment']}`]
      .filter(Boolean)
      .join('\n');
    downloadFile(
      `booking-${(c.reference || data.booking_id).toLowerCase()}.ics`,
      buildIcs({
        uid: `${data.booking_id}@pinehurst`,
        start: data.start_time,
        end: data.end_time,
        summary: `${c.event} – ${data.room_name}`,
        location,
        description,
      }),
      'text/calendar'
    );
  }

  async function copyDetails() {
    try {
      await navigator.clipboard.writeText(plainText(c, status));
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      <div className="no-print" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button type="button" className="btn btn-primary" onClick={savePdf}>Save as PDF</button>
        <button type="button" className="btn btn-secondary" onClick={addToCalendar}>Add to calendar</button>
        <button type="button" className="btn btn-secondary" onClick={copyDetails}>{copied ? 'Copied' : 'Copy details'}</button>
      </div>
      <p className="no-print field-hint" style={{ margin: '0 0 12px' }}>
        To save a PDF, choose "Save as PDF" as the destination in the window that opens.
      </p>

      <div className="confirmation-doc card" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 500 }}>{c.brand}</div>
            <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>{c.subtitle}</div>
          </div>
          <span className={`badge badge-${badge.tone}`}>{badge.label}</span>
        </div>

        {status === 'pending' && (
          <p style={{ margin: '14px 0 0', padding: '10px 12px', fontSize: 13, color: 'var(--wait)', background: 'var(--wait-bg)', border: '1px solid var(--wait-bd)', borderRadius: 8 }}>
            This is a request — the office hasn't confirmed it yet. The details below apply once it is.
          </p>
        )}

        <p style={{ margin: '16px 0 0', color: 'var(--ink)' }}>Dear {c.recipient_name},</p>
        <p style={{ margin: '4px 0 0' }}>{c.intro}</p>

        <h3 style={{ margin: '20px 0 6px' }}>Booking details</h3>
        <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'minmax(110px, 160px) 1fr', gap: '6px 12px', fontSize: 14 }}>
          {c.details.map((d) => (
            <div key={d.label} style={{ display: 'contents' }}>
              <dt style={{ color: 'var(--ink-2)' }}>{d.label}</dt>
              <dd style={{ margin: 0, fontWeight: 600, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{d.value}</dd>
            </div>
          ))}
          <div style={{ display: 'contents' }}>
            <dt style={{ color: 'var(--ink-2)' }}>Length</dt>
            <dd style={{ margin: 0, fontWeight: 600, color: 'var(--ink)' }}>{formatSlot(data.start_time, data.end_time).split(' · ').pop()}</dd>
          </div>
        </dl>

        {(c.room_notes.setup_notes || c.room_notes.booking_message) && (
          <div style={{ marginTop: 14, fontSize: 14 }}>
            {c.room_notes.setup_notes && (
              <p style={{ margin: '0 0 6px' }}>
                <strong style={{ color: 'var(--ink)' }}>Please leave the room like this:</strong> {c.room_notes.setup_notes}
              </p>
            )}
            {c.room_notes.booking_message && <p style={{ margin: 0, whiteSpace: 'pre-line' }}>{c.room_notes.booking_message}</p>}
          </div>
        )}

        <h3 style={{ margin: '20px 0 6px' }}>{c.reminders_heading}</h3>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, lineHeight: 1.55, color: 'var(--ink)' }}>
          {c.reminders.map((r) => (
            <li key={r} style={{ marginBottom: 6 }}>{r}</li>
          ))}
        </ul>
        {c.extra_notes.map((n) => (
          <p key={n} style={{ margin: '14px 0 0' }}>{n}</p>
        ))}

        <p style={{ margin: '14px 0 0', padding: '10px 12px', fontSize: 14, color: 'var(--ink)', background: 'var(--wait-bg)', borderRadius: 8 }}>
          {c.access_note}
        </p>
        {c.cancellation && <p style={{ margin: '14px 0 0' }}>{c.cancellation}</p>}
        {c.closing.map((n) => (
          <p key={n} style={{ margin: '14px 0 0' }}>{n}</p>
        ))}
        <p style={{ margin: '18px 0 0', color: 'var(--ink)' }}>
          Kind regards,<br />
          <strong>{c.sign_off}</strong>
        </p>
      </div>
    </div>
  );
}
