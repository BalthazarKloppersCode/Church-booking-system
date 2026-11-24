// What the event is, as written on the admin calendar: the detail typed for "Other" when there is
// one ("Wedding rehearsal"), otherwise the purpose picked from the list ("Bible study").
export function eventName(booking) {
  const detail = (booking.purpose_other || '').trim();
  return detail || (booking.purpose || '').trim() || 'Booking';
}

// "Bible study — Main Hall — Youth Group (20)", for the month view and tooltips.
export function eventTitle(booking) {
  return `${eventName(booking)} — ${booking.room_name} — ${booking.congregation} (${booking.headcount})`;
}
