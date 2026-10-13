import { formatDay } from './formatDate';

// One plain sentence about what the "New booking" sheet just created, so a repeat
// that produced one booking (or fifty) is never a surprise.
export function describeCreated(result) {
  const bookings = result?.bookings || [];
  const starts = [...new Set(bookings.map((b) => b.start_time))].sort();
  if (!starts.length) return 'Booking created.';
  const roomCount = new Set(bookings.map((b) => b.room_name)).size;
  const inRooms = roomCount > 1 ? ` in ${roomCount} rooms` : '';
  if (starts.length === 1) return `Booking created for ${formatDay(starts[0])}${inRooms}.`;
  return `${starts.length} bookings created${inRooms}: ${formatDay(starts[0])} to ${formatDay(starts[starts.length - 1])}.`;
}
