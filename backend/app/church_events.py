"""
Which rooms the church-calendar events occupy.

Events come from Google Calendar, which knows nothing about our rooms, so an
admin assigns rooms to an event here and the assignment is stored in our own
database, keyed by the event's UID. A repeating event is a single UID, so one
assignment covers every date it repeats on — set "Sunday Service" to the Main
Hall once and every Sunday blocks it.

An event with rooms assigned counts as a booking for availability: those rooms
show as taken, can't be booked over, and are offered as busy in room
suggestions. Events with no rooms stay informational, as before.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from app import google_calendar
from app.database import bookings_collection, event_rooms_collection


async def assignments_for(uids: list[str]) -> dict[str, list[str]]:
    """uid -> room ids, for the given event UIDs."""
    wanted = [u for u in set(uids) if u]
    if not wanted:
        return {}
    return {doc["uid"]: doc.get("room_ids", []) async for doc in event_rooms_collection.find({"uid": {"$in": wanted}})}


async def events_with_rooms(start: datetime, end: datetime) -> list[dict]:
    """Church-calendar events in the window, each with the rooms assigned to it."""
    events = await google_calendar.list_external_events(start, end)
    rooms = await assignments_for([e.get("uid", "") for e in events])
    return [{**e, "room_ids": rooms.get(e.get("uid", ""), [])} for e in events]


async def blocking_event(room_id: str, start: datetime, end: datetime) -> Optional[dict]:
    """The church event holding this room during the window, or None.

    Cheap when nothing is assigned: it only reads the feed once some event has
    this room, and then only expands those events."""
    uids = {doc["uid"] async for doc in event_rooms_collection.find({"room_ids": room_id})}
    if not uids:
        return None
    for event in await google_calendar.list_external_events(start, end, uids=uids):
        if event.get("uid") in uids and event["start_time"] < end and event["end_time"] > start:
            return event
    return None


def _utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt.tzinfo is None else dt.isoformat()


async def clashes(uid: str, room_ids: list[str], days: int = 90, limit: int = 50) -> list[dict]:
    """Existing bookings that overlap this event's upcoming dates in its rooms —
    assigning a room doesn't cancel anything, so the admin needs to see these."""
    if not room_ids:
        return []
    now = datetime.utcnow()
    found = []
    for event in await google_calendar.list_external_events(now, now + timedelta(days=days), uids={uid}):
        if event.get("uid") != uid:
            continue
        async for booking in bookings_collection.find(
            {
                "room_id": {"$in": room_ids},
                "status": {"$in": ["pending", "approved"]},
                "start_time": {"$lt": event["end_time"]},
                "end_time": {"$gt": event["start_time"]},
            }
        ):
            found.append(
                {
                    "booking_id": str(booking["_id"]),
                    "room_name": booking.get("room_name", ""),
                    "congregation": booking.get("congregation", ""),
                    "start_time": _utc(booking["start_time"]),
                    "end_time": _utc(booking["end_time"]),
                    "event_title": event["title"],
                    "event_start": _utc(event["start_time"]),
                }
            )
            if len(found) >= limit:
                return found
    return found
