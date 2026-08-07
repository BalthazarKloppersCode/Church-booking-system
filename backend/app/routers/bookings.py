from datetime import datetime, timedelta
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import get_current_admin
from app.config import settings
from app.database import bookings_collection, rooms_collection
from app.models import Booking, BookingCreate, BookingStatus
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
async def create_booking(request: Request, payload: BookingCreate):
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

    within_auto_window = (payload.start_time - datetime.utcnow()) <= timedelta(
        days=settings.auto_approve_window_days
    )
    needs_approval = payload.is_private_event or not within_auto_window
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

    if needs_approval:
        await notify_booking_pending(created, room)
        await notify_admin_new_request(created, room)
    else:
        await notify_booking_confirmed(created, room)

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


@router.post("/{booking_id}/cancel", response_model=Booking)
@limiter.limit("20/minute")
async def cancel_booking(request: Request, booking_id: str, email: str):
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
    return _booking_out(updated)
