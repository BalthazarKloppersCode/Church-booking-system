"""
DB-aware orchestration around google_calendar.py's raw API calls: creates,
updates, or deletes the Google Calendar event tied to a booking's lifecycle
and persists the resulting event id back onto the booking document.

Every function here is meant to run via FastAPI's BackgroundTasks — never
awaited directly in a request handler — so a slow or unreachable Google API
never delays a booking response. If sync is disabled (no service account
configured), google_calendar's functions are no-ops and these simply do
nothing extra.
"""
import asyncio

from app import google_calendar
from app.database import bookings_collection


async def sync_created(booking: dict, room_name: str) -> None:
    """Booking just became approved and has no Google event yet."""
    event_id = await google_calendar.create_event(booking, room_name)
    if event_id:
        await bookings_collection.update_one(
            {"_id": booking["_id"]}, {"$set": {"google_event_id": event_id}}
        )


async def sync_updated(booking: dict, room_name: str) -> None:
    """An approved booking's time/room/details changed."""
    event_id = booking.get("google_event_id")
    if event_id:
        await google_calendar.update_event(event_id, booking, room_name)
    else:
        # Wasn't synced yet (e.g. edited before the create call landed) —
        # fall back to creating it now instead of silently dropping it.
        await sync_created(booking, room_name)


async def sync_removed(booking: dict) -> None:
    """Booking was cancelled, rejected, or deleted — remove its event, if any."""
    event_id = booking.get("google_event_id")
    if event_id:
        await google_calendar.delete_event(event_id)


async def sync_created_many(bookings: list[dict], room_name: str) -> None:
    """Bulk variant for a freshly-created recurring series (all pre-approved)."""

    async def _one(b: dict):
        event_id = await google_calendar.create_event(b, room_name)
        if event_id:
            await bookings_collection.update_one({"_id": b["_id"]}, {"$set": {"google_event_id": event_id}})

    await asyncio.gather(*(_one(b) for b in bookings))


async def sync_removed_many(bookings: list[dict]) -> None:
    """Bulk variant for cancelling a whole recurring series at once."""
    await asyncio.gather(*(sync_removed(b) for b in bookings if b.get("google_event_id")))
