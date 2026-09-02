from datetime import datetime, timedelta
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app import calendar_sync, google_calendar
from app.auth import get_current_admin, get_current_user_optional
from app.config import settings
from app.database import areas_collection, bookings_collection, congregations_collection, rooms_collection
from app.models import Booking, BookingCreate, BookingStatus, CalendarEntry, ExternalCalendarEvent
from app.notifications import (
    notify_booking_confirmed,
    notify_booking_pending,
    notify_admin_new_request,
)
from app.rate_limit import limiter
from app.routers.rooms import _is_room_free, _room_out

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def _booking_out(doc: dict) -> Booking:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return Booking(**doc)


@router.post("", response_model=Booking)
@limiter.limit("10/minute")
async def create_booking(
    request: Request,
    payload: BookingCreate,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user_optional),
):
    room = await rooms_collection.find_one({"_id": ObjectId(payload.room_id)})
    if not room:
        raise HTTPException(404, "Room not found")

    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "End time must be after start time")

    if payload.headcount > room["capacity"]:
        raise HTTPException(
            400,
            f"{room['name']} can only hold {room['capacity']} people — please pick a larger room.",
        )

    free = await _is_room_free(payload.room_id, payload.start_time, payload.end_time)
    if not free:
        raise HTTPException(409, "This room is already booked for that time slot")

    if not user:
        raise HTTPException(403, "You must be logged in to make a booking — log in first, then try again.")

    # The area that governs approval rules comes from the logged-in user's own
    # assignment (set when the admin created their account), not whatever
    # congregation they typed into the form — that's what makes the perk
    # tied to who they are rather than what they claim. Fall back to the
    # congregation's area only for users created before area_id existed.
    area = None
    if user.get("area_id"):
        area = await areas_collection.find_one({"_id": ObjectId(user["area_id"])})
    else:
        congregation_doc = await congregations_collection.find_one({"name": payload.congregation})
        if congregation_doc and congregation_doc.get("area_id"):
            area = await areas_collection.find_one({"_id": ObjectId(congregation_doc["area_id"])})

    # The 2-week auto-approve window only applies to areas that explicitly opt
    # out of always-requires-approval (currently just Northern Hub). No area
    # match, or an area that hasn't opted out, defaults to needing approval.
    area_always_requires_approval = True if area is None else area.get("always_requires_approval", True)

    within_auto_window = (payload.start_time - datetime.utcnow()) <= timedelta(
        days=settings.auto_approve_window_days
    )
    # A room can force approval on its own too (e.g. Hebrews, the barista
    # shop add-on) regardless of the booker's area or how far out it is.
    room_always_requires_approval = room.get("always_requires_approval", False)
    needs_approval = (
        payload.is_private_event
        or area_always_requires_approval
        or not within_auto_window
        or room_always_requires_approval
    )
    status = BookingStatus.pending if needs_approval else BookingStatus.approved

    now = datetime.utcnow()
    booking_doc = {
        **payload.model_dump(),
        "room_name": room["name"],
        "status": status.value,
        "admin_note": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await bookings_collection.insert_one(booking_doc)
    created = await bookings_collection.find_one({"_id": result.inserted_id})
    booking_out = _booking_out(created)

    # Notifications hit external APIs (Resend/WhatsApp) — run them after the
    # response is sent instead of making the booker wait on that round-trip.
    if needs_approval:
        background_tasks.add_task(notify_booking_pending, created, room)
        background_tasks.add_task(notify_admin_new_request, created, room)
    else:
        background_tasks.add_task(notify_booking_confirmed, created, room)
        background_tasks.add_task(calendar_sync.sync_created, created, room["name"])

    return booking_out


@router.get("", response_model=List[Booking])
async def list_bookings(
    email: Optional[str] = None,
    room_id: Optional[str] = None,
    congregation: Optional[str] = None,
    status: Optional[BookingStatus] = None,
    start_after: Optional[datetime] = None,
    start_before: Optional[datetime] = None,
):
    """
    Public-ish listing endpoint used by:
    - a booker checking their own bookings (filter by email)
    - the admin calendar / room grid (filter by date range / room / status)
    No auth required for read access since it powers the public "is this
    room free" calendar view; sensitive requester details are still
    returned, so lock this down with auth if you make it internet-public
    beyond your congregation.
    """
    query: dict = {}
    if email:
        query["email"] = email
    if room_id:
        query["room_id"] = room_id
    if congregation:
        query["congregation"] = congregation
    if status:
        query["status"] = status.value
    if start_after or start_before:
        query["start_time"] = {}
        if start_after:
            query["start_time"]["$gte"] = start_after
        if start_before:
            query["start_time"]["$lte"] = start_before

    bookings = [_booking_out(b) async for b in bookings_collection.find(query).sort("start_time", 1)]
    return bookings


@router.get("/calendar", response_model=List[CalendarEntry])
async def list_bookings_calendar(
    start_after: Optional[datetime] = None,
    start_before: Optional[datetime] = None,
):
    """
    Feeds the booker-facing "browse the calendar" view. Deliberately returns
    only room/time/status — never requester name, congregation, email, or
    phone — so a booker's browser never receives another congregation's
    contact details just to show what's free. Only pending/approved
    bookings are included, since those are the only statuses that actually
    block a time slot.
    """
    query: dict = {"status": {"$in": [BookingStatus.pending.value, BookingStatus.approved.value]}}
    if start_after or start_before:
        query["start_time"] = {}
        if start_after:
            query["start_time"]["$gte"] = start_after
        if start_before:
            query["start_time"]["$lte"] = start_before

    projection = {"_id": 0, "room_name": 1, "start_time": 1, "end_time": 1, "status": 1}
    return [
        CalendarEntry(**b)
        async for b in bookings_collection.find(query, projection).sort("start_time", 1)
    ]


@router.get("/calendar/external", response_model=List[ExternalCalendarEvent])
async def list_external_calendar_events(
    start_after: Optional[datetime] = None,
    start_before: Optional[datetime] = None,
):
    """
    Events already on the synced church Google Calendar that didn't come
    from a booking made in this app — lets the booker/admin calendar views
    show existing church events (services, etc.) alongside real bookings,
    without duplicating the ones this app already pushed there itself.
    Returns an empty list if Google Calendar sync isn't configured.
    """
    now = datetime.utcnow()
    start = start_after or (now - timedelta(days=7))
    end = start_before or (now + timedelta(days=90))
    events = await google_calendar.list_external_events(start, end)
    return [ExternalCalendarEvent(**e) for e in events]


@router.post("/{booking_id}/cancel", response_model=Booking)
@limiter.limit("20/minute")
async def cancel_booking(request: Request, booking_id: str, email: str, background_tasks: BackgroundTasks):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking["email"].lower() != email.lower():
        raise HTTPException(403, "You can only cancel your own bookings")

    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": BookingStatus.cancelled.value, "updated_at": datetime.utcnow()}},
    )
    updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    background_tasks.add_task(calendar_sync.sync_removed, booking)
    return _booking_out(updated)
