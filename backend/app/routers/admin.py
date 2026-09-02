import asyncio
import calendar
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Tuple
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.auth import (
    create_access_token,
    get_current_admin,
    get_current_admin_optional,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import admins_collection, bookings_collection, rooms_collection
from app.models import (
    AdminBookingCreate,
    AdminBookingUpdate,
    AdminCreate,
    AdminLogin,
    AdminOut,
    Booking,
    BookingAdminAction,
    BookingStatus,
    RecurrenceRule,
    Token,
)
from app import calendar_sync
from app.notifications import notify_booking_confirmed, notify_booking_decision
from app.rate_limit import limiter
from app.routers.bookings import _booking_out
from app.routers.rooms import _is_room_free

router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_RECURRING_OCCURRENCES = 104  # 2 years weekly — a sane ceiling against fat-fingered ranges


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _generate_occurrences(
    start: datetime, end: datetime, recurrence: RecurrenceRule
) -> List[Tuple[datetime, datetime]]:
    duration = end - start
    occurrences = [(start, end)]
    month_offset = 0
    while True:
        if recurrence.frequency == "monthly":
            # Always step from the original start, not the previous occurrence —
            # otherwise a 31st gets clamped to Feb 28 and every month after
            # drifts to the 28th instead of returning to the 31st.
            month_offset += 1
            next_start = _add_months(start, month_offset)
        else:
            next_start = occurrences[-1][0] + timedelta(days=7 if recurrence.frequency == "weekly" else 14)
        if next_start.date() > recurrence.until.date():
            break
        occurrences.append((next_start, next_start + duration))
        if len(occurrences) > MAX_RECURRING_OCCURRENCES:
            raise HTTPException(
                400,
                f"That recurrence produces more than {MAX_RECURRING_OCCURRENCES} bookings — shorten the range.",
            )
    return occurrences


@router.post("/register", response_model=AdminOut)
@limiter.limit("5/hour")
async def register_admin(request: Request, payload: AdminCreate, requester=Depends(get_current_admin_optional)):
    """
    Creates an admin account. Before any admin exists, this requires
    ADMIN_SETUP_SECRET (set in the server's env) passed as `setup_secret` —
    use it once to bootstrap your first admin, then rotate/remove it.
    Once at least one admin exists, only an already-logged-in admin may
    create further admin accounts.
    """
    existing = await admins_collection.find_one({"email": payload.email})
    if existing:
        raise HTTPException(400, "An admin with this email already exists")

    any_admin_exists = await admins_collection.find_one({}) is not None
    if any_admin_exists:
        if requester is None:
            raise HTTPException(401, "Log in as an existing admin to create another admin account")
    else:
        if not settings.admin_setup_secret:
            raise HTTPException(
                503,
                "Admin setup is not configured — set ADMIN_SETUP_SECRET on the server before creating the first admin",
            )
        if payload.setup_secret != settings.admin_setup_secret:
            raise HTTPException(403, "Invalid setup secret")

    doc = {
        "name": payload.name,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
    }
    result = await admins_collection.insert_one(doc)
    return AdminOut(id=str(result.inserted_id), name=payload.name, email=payload.email)


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, payload: AdminLogin):
    admin = await admins_collection.find_one({"email": payload.email})
    if not admin or not verify_password(payload.password, admin["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    token = create_access_token(str(admin["_id"]))
    admin_out = AdminOut(id=str(admin["_id"]), name=admin["name"], email=admin["email"])
    return Token(access_token=token, admin=admin_out)


@router.get("/me", response_model=AdminOut)
async def me(admin=Depends(get_current_admin)):
    return AdminOut(id=str(admin["_id"]), name=admin["name"], email=admin["email"])


@router.get("/approvals", response_model=List[Booking])
async def pending_approvals(admin=Depends(get_current_admin)):
    bookings = [
        _booking_out(b)
        async for b in bookings_collection.find({"status": BookingStatus.pending.value}).sort(
            "start_time", 1
        )
    ]
    return bookings


@router.post("/bookings/{booking_id}/approve", response_model=Booking)
async def approve_booking(
    booking_id: str,
    action: BookingAdminAction,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")

    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {
            "$set": {
                "status": BookingStatus.approved.value,
                "admin_note": action.admin_note,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    room = await rooms_collection.find_one({"_id": ObjectId(booking["room_id"])})
    background_tasks.add_task(notify_booking_decision, updated, room, approved=True)
    background_tasks.add_task(calendar_sync.sync_created, updated, room["name"])
    return _booking_out(updated)


@router.post("/bookings/{booking_id}/reject", response_model=Booking)
async def reject_booking(
    booking_id: str,
    action: BookingAdminAction,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")

    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {
            "$set": {
                "status": BookingStatus.rejected.value,
                "admin_note": action.admin_note,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    room = await rooms_collection.find_one({"_id": ObjectId(booking["room_id"])})
    background_tasks.add_task(notify_booking_decision, updated, room, approved=False)
    # Rejecting only ever happens from "pending", which never had a Google
    # event yet — but defensively clear one if it's somehow already there.
    if booking.get("google_event_id"):
        background_tasks.add_task(calendar_sync.sync_removed, updated)
    return _booking_out(updated)


@router.post("/bookings", response_model=dict)
async def admin_create_booking(
    payload: AdminBookingCreate, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)
):
    """
    Admin-authored bookings (e.g. clicking a slot on the calendar) skip the
    normal approval workflow entirely — the admin is the approver, so these
    are created as 'approved' immediately. If `recurrence` is set, one
    booking is created per occurrence, all sharing a series_id; every
    occurrence is checked for room conflicts before any of them are created,
    so a series is all-or-nothing rather than partially booked.
    """
    room = await rooms_collection.find_one({"_id": ObjectId(payload.room_id)})
    if not room:
        raise HTTPException(404, "Room not found")
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "End time must be after start time")
    if payload.headcount > room["capacity"]:
        raise HTTPException(
            400, f"{room['name']} can only hold {room['capacity']} people — please pick a larger room."
        )

    if payload.recurrence:
        occurrences = _generate_occurrences(payload.start_time, payload.end_time, payload.recurrence)
    else:
        occurrences = [(payload.start_time, payload.end_time)]

    # Each conflict check is its own DB round-trip — for a long recurring
    # series (up to MAX_RECURRING_OCCURRENCES) that's a lot of them, so run
    # them concurrently rather than one at a time.
    is_free = await asyncio.gather(
        *(_is_room_free(payload.room_id, start, end) for start, end in occurrences)
    )
    conflicts = [
        start.strftime("%Y-%m-%d")
        for (start, end), free in zip(occurrences, is_free)
        if not free
    ]
    if conflicts:
        raise HTTPException(
            409, f"{room['name']} is already booked on: {', '.join(conflicts)} — nothing was created."
        )

    series_id = uuid4().hex if len(occurrences) > 1 else None
    now = datetime.utcnow()
    base_fields = payload.model_dump(exclude={"recurrence", "start_time", "end_time"})
    docs = [
        {
            **base_fields,
            "start_time": start,
            "end_time": end,
            "room_name": room["name"],
            "status": BookingStatus.approved.value,
            "admin_note": None,
            "series_id": series_id,
            "created_at": now,
            "updated_at": now,
        }
        for start, end in occurrences
    ]
    result = await bookings_collection.insert_many(docs)
    # We already have every field of every created doc in `docs` — no need
    # to read them back from the DB one at a time, we just have to attach
    # the ids Mongo assigned.
    created_docs = [{**doc, "_id": _id} for doc, _id in zip(docs, result.inserted_ids)]

    background_tasks.add_task(notify_booking_confirmed, created_docs[0], room)
    background_tasks.add_task(calendar_sync.sync_created_many, created_docs, room["name"])

    return {
        "created_count": len(created_docs),
        "series_id": series_id,
        "bookings": [_booking_out(d) for d in created_docs],
    }


@router.post("/bookings/{booking_id}/cancel", response_model=Booking)
async def admin_cancel_booking(booking_id: str, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")
    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": BookingStatus.cancelled.value, "updated_at": datetime.utcnow()}},
    )
    updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    background_tasks.add_task(calendar_sync.sync_removed, booking)
    return _booking_out(updated)


@router.patch("/bookings/{booking_id}", response_model=Booking)
async def admin_update_booking(
    booking_id: str, payload: AdminBookingUpdate, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)
):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "status" in update_data:
        update_data["status"] = update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]
    if "room_id" in update_data:
        room = await rooms_collection.find_one({"_id": ObjectId(update_data["room_id"])})
        if not room:
            raise HTTPException(404, "Room not found")
        update_data["room_name"] = room["name"]

    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await bookings_collection.update_one({"_id": ObjectId(booking_id)}, {"$set": update_data})
    updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})

    # Keep the Google Calendar event in step with whatever changed —
    # removed if the booking is no longer live, created/updated otherwise.
    if update_data:
        if updated["status"] in (BookingStatus.cancelled.value, BookingStatus.rejected.value):
            background_tasks.add_task(calendar_sync.sync_removed, updated)
        elif updated["status"] == BookingStatus.approved.value:
            background_tasks.add_task(calendar_sync.sync_updated, updated, updated["room_name"])

    return _booking_out(updated)


@router.delete("/bookings/{booking_id}")
async def admin_delete_booking(booking_id: str, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")
    await bookings_collection.delete_one({"_id": ObjectId(booking_id)})
    background_tasks.add_task(calendar_sync.sync_removed, booking)
    return {"ok": True}


@router.post("/bookings/series/{series_id}/cancel")
async def admin_cancel_series(series_id: str, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    # Snapshot which bookings had a synced Google event *before* the bulk
    # update, since that's the only place their google_event_id is visible.
    to_unsync = [
        b
        async for b in bookings_collection.find(
            {
                "series_id": series_id,
                "status": {"$nin": [BookingStatus.cancelled.value, BookingStatus.rejected.value]},
                "google_event_id": {"$ne": None},
            }
        )
    ]
    result = await bookings_collection.update_many(
        {
            "series_id": series_id,
            "status": {"$nin": [BookingStatus.cancelled.value, BookingStatus.rejected.value]},
        },
        {"$set": {"status": BookingStatus.cancelled.value, "updated_at": datetime.utcnow()}},
    )
    background_tasks.add_task(calendar_sync.sync_removed_many, to_unsync)
    return {"cancelled_count": result.modified_count}


@router.get("/dashboard")
async def dashboard_stats(admin=Depends(get_current_admin)):
    now = datetime.utcnow()
    week_end = now + timedelta(days=7)

    async def _fetch_upcoming():
        return [
            _booking_out(b)
            async for b in bookings_collection.find(
                {"status": BookingStatus.approved.value, "start_time": {"$gte": now}}
            )
            .sort("start_time", 1)
            .limit(10)
        ]

    # These four queries don't depend on each other — run them concurrently
    # instead of waiting on each round-trip in turn.
    pending_count, upcoming_week_count, total_rooms, upcoming = await asyncio.gather(
        bookings_collection.count_documents({"status": BookingStatus.pending.value}),
        bookings_collection.count_documents(
            {
                "status": BookingStatus.approved.value,
                "start_time": {"$gte": now, "$lte": week_end},
            }
        ),
        rooms_collection.count_documents({"active": True}),
        _fetch_upcoming(),
    )

    return {
        "pending_approvals": pending_count,
        "bookings_this_week": upcoming_week_count,
        "active_rooms": total_rooms,
        "next_bookings": upcoming,
    }


@router.get("/analytics")
async def analytics(days: int = 30, admin=Depends(get_current_admin)):
    """
    Powers the dashboard charts. `days` is the shared adjustable window
    (7/30/90) for the by-congregation/by-purpose/by-room/weekly breakdowns.
    avg_approval_hours always looks at a fixed trailing 30 days, independent
    of `days`, since it's a fixed operational metric rather than a chart.

    All breakdowns are grouped by created_at (when the request was made, not
    the event's start_time) and exclude cancelled/rejected bookings, so they
    reflect real booking demand in the period.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(days=days)
    approval_window_start = now - timedelta(days=30)

    approval_hours: List[float] = []
    async for b in bookings_collection.find(
        {"status": BookingStatus.approved.value, "created_at": {"$gte": approval_window_start}}
    ):
        if b["updated_at"] > b["created_at"]:
            approval_hours.append((b["updated_at"] - b["created_at"]).total_seconds() / 3600)
    avg_approval_hours = round(sum(approval_hours) / len(approval_hours), 1) if approval_hours else None

    by_congregation: Counter = Counter()
    by_purpose: Counter = Counter()
    by_room: Counter = Counter()
    weekly: Counter = Counter()

    async for b in bookings_collection.find(
        {
            "created_at": {"$gte": window_start},
            "status": {"$nin": [BookingStatus.cancelled.value, BookingStatus.rejected.value]},
        }
    ):
        by_congregation[b["congregation"]] += 1
        by_purpose[b.get("purpose") or "Other"] += 1
        by_room[b["room_name"]] += 1
        week_start = b["created_at"] - timedelta(days=b["created_at"].weekday())
        weekly[week_start.strftime("%Y-%m-%d")] += 1

    def _ranked(counter: Counter) -> List[dict]:
        return [
            {"label": label, "count": count}
            for label, count in sorted(counter.items(), key=lambda item: -item[1])
        ]

    return {
        "avg_approval_hours": avg_approval_hours,
        "by_congregation": _ranked(by_congregation),
        "by_purpose": _ranked(by_purpose),
        "by_room": _ranked(by_room),
        "weekly": sorted(
            [{"week_start": k, "count": v} for k, v in weekly.items()],
            key=lambda item: item["week_start"],
        ),
    }
