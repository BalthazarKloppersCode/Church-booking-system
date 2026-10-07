// One place that turns a booking's raw status into the words and colour shown
// to a person (DESIGN_DIRECTION.md §6 Badges, §9: never a bare "pending" — say
// who decides). Only confirmed / awaiting / declined carry colour; cancelled
// and past are history, not problems.

export function bookingBadge(booking, now = new Date()) {
  switch (booking.status) {
    case 'pending':
      return { label: 'Awaiting the office', tone: 'pending' };
    case 'rejected':
      return { label: 'Declined', tone: 'rejected' };
    case 'cancelled':
      return { label: 'Cancelled', tone: 'cancelled' };
    case 'approved':
      return new Date(booking.end_time) < now
        ? { label: 'Past', tone: 'cancelled' }
        : { label: 'Confirmed', tone: 'approved' };
    default:
      return { label: booking.status, tone: 'cancelled' };
  }
}
