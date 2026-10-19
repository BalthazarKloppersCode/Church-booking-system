"""
The shareable "private events only" link.

Anyone with the link can ask for the venue for a private event (wedding,
birthday, funeral, other) without an account. Nothing it creates is ever
confirmed on its own: every request is a private event, waiting for the office.

Because it is open to the internet, it is deliberately narrow and defended:
- it can only create private-event requests (the caller can't pick the status);
- a hidden honeypot field catches simple bots;
- requests are rate limited, and one person can only have a few waiting at once
  (a waiting request holds its room, so unlimited requests could block the venue);
- dates must be sensible, rooms must exist, and a request can't be made for a
  room that is already taken at that time.
"""
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app import church_events
from app.config import settings
from app.database import bookings_collection, rooms_collection
from app.models import Booking, BookingStatus, PrivateEventRequest, PRIVATE_LINK_PURPOSES
from app.notifications import notify_admin_new_request, notify_booking_pending
from app.rate_limit import limiter
from app.routers.bookings import _booking_out
from app.routers.rooms import _is_room_free

router = APIRouter(prefix="/api/public", tags=["public"])

MAX_WAITING_PER_PERSON = 3
MAX_DAYS_AHEAD = 548  # about 18 months
MAX_EVENT_HOURS = 24
SOURCE = "private_link"


@router.get("/private-events/status")
async def private_link_status():
    """Lets the page say "this link is switched off" instead of failing at the last step."""
    return {"enabled": settings.private_event_link_enabled, "purposes": PRIVATE_LINK_PURPOSES}


@router.post("/private-events", response_model=Booking)
@limiter.limit("60/hour")
async def request_private_event(request: Request, payload: PrivateEventRequest, background_tasks: BackgroundTasks):
    if not settings.private_event_link_enabled:
        raise HTTPException(403, "This request link is switched off at the moment. Please contact the office.")
    if payload.website.strip():
        raise HTTPException(400, "We couldn't submit this request.")
    if not payload.accepted_conditions:
        raise HTTPException(400, "Please accept the venue booking conditions to send your request.")

    now = datetime.utcnow()
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "The end time must be after the start time")
    if payload.start_time <= now:
        raise HTTPException(400, "Please choose a date and time in the future")
    if payload.start_time > now + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(400, "That date is too far ahead — please contact the office")
    if payload.end_time - payload.start_time > timedelta(hours=MAX_EVENT_HOURS):
        raise HTTPException(400, "A request can be for at most 24 hours")

    room = await rooms_collection.find_one({"_id": ObjectId(payload.room_id)}) if ObjectId.is_valid(payload.room_id) else None
    if not room or not room.get("active", True):
        raise HTTPException(404, "Room not found")
    if payload.headcount > room["capacity"]:
        raise HTTPException(400, f"{room['name']} can only hold {room['capacity']} people — please pick a larger room.")

    # A waiting request holds its room, so one person can't queue up many of them.
    waiting = await bookings_collection.count_documents(
        {
            "status": BookingStatus.pending.value,
            "source": SOURCE,
            "$or": [{"email": {"$regex": f"^{_escape(payload.email)}$", "$options": "i"}}, {"phone": payload.phone.strip()}],
        }
    )
    if waiting >= MAX_WAITING_PER_PERSON:
        raise HTTPException(
            429,
            f"You already have {MAX_WAITING_PER_PERSON} requests waiting for the office. Please wait for an answer before sending more.",
        )

    if not await _is_room_free(payload.room_id, payload.start_time, payload.end_time):
        event = await church_events.blocking_event(payload.room_id, payload.start_time, payload.end_time)
        if event:
            raise HTTPException(409, f"{room['name']} is in use for “{event['title']}” at that time")
        raise HTTPException(409, "This room is already booked for that time slot")

    doc = {
        "room_id": payload.room_id,
        "room_name": room["name"],
        "requester_name": payload.requester_name.strip(),
        "congregation": (payload.congregation or "").strip() or "Private event request",
        "email": payload.email,
        "phone": payload.phone.strip(),
        "headcount": payload.headcount,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "purpose": payload.purpose,
        "purpose_other": (payload.purpose_other or "").strip() or None,
        "notes": (payload.notes or "").strip() or None,
        "is_private_event": True,
        "accepted_conditions": True,
        "status": BookingStatus.pending.value,
        "admin_note": None,
        "source": SOURCE,
        "created_at": now,
        "updated_at": now,
    }
    result = await bookings_collection.insert_one(doc)
    created = await bookings_collection.find_one({"_id": result.inserted_id})

    background_tasks.add_task(notify_booking_pending, created, room)
    background_tasks.add_task(notify_admin_new_request, created, room)
    return _booking_out(created)


def _escape(text: str) -> str:
    import re

    return re.escape(text.strip())
