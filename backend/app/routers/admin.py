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
from app.database import admins_collection, bookings_collection, event_rooms_collection, rooms_collection
from app.models import (
    AdminBookingCreate,
    AdminBookingUpdate,
    AdminCreate,
    AdminLogin,
    AdminOut,
    Booking,
    BookingAdminAction,
    BookingStatus,
    EventRoomsUpdate,
    RecurrenceRule,
    Token,
)
from app import calendar_sync, church_events
from app.date_format import format_day, to_local
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


def _join_names(names: List[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _combined_room(rooms: List[dict]) -> dict:
    """
    One room-shaped record standing in for every room of a multi-room booking,
    so the single confirmation names them all and lists the equipment, location
    and set-up notes of each (instead of only the first room's).
    """
    if len(rooms) == 1:
        return rooms[0]

    def unique(values):
        return list(dict.fromkeys(v for v in values if v))

    def per_room(key, separator):
        notes = [(r["name"], (r.get(key) or "").strip()) for r in rooms]
        notes = [(name, text) for name, text in notes if text]
        # Every room says the same thing (or only one has a note): no need to label it.
        if len({text for _, text in notes}) <= 1 and len(notes) in (0, 1, len(rooms)):
            return notes[0][1] if notes else None
        return separator.join(f"{name}: {text}" for name, text in notes)

    return {
        **rooms[0],
        "name": _join_names([r["name"] for r in rooms]),
        "amenities": unique(a for r in rooms for a in r.get("amenities", [])),
        "location": "; ".join(unique(r.get("location") for r in rooms)) or None,
        "setup_notes": per_room("setup_notes", "\n"),
        "booking_message": per_room("booking_message", "\n\n"),
    }


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

    An event can take several rooms at once (`room_ids`): each room gets its own
    booking for the same time, tied together by a group_id so they can be
    cancelled together. The headcount is the whole event's, so it only has to fit
    in the rooms combined. Every room of every occurrence is checked first.
    """
    rooms = []
    for room_id in payload.room_ids:
        room = await rooms_collection.find_one({"_id": ObjectId(room_id)}) if ObjectId.is_valid(room_id) else None
        if not room:
            raise HTTPException(404, "Room not found")
        rooms.append(room)
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "End time must be after start time")
    if len(rooms) == 1:
        if payload.headcount > rooms[0]["capacity"]:
            raise HTTPException(
                400, f"{rooms[0]['name']} can only hold {rooms[0]['capacity']} people — please pick a larger room."
            )
    else:
        total = sum(r["capacity"] for r in rooms)
        if payload.headcount > total:
            raise HTTPException(
                400, f"These rooms together hold {total} people — add another room or lower the headcount."
            )

    if payload.recurrence:
        occurrences = _generate_occurrences(payload.start_time, payload.end_time, payload.recurrence)
        if len(occurrences) < 2:
            raise HTTPException(
                400, "That repeat only produces one booking — pick an 'until' date after the first booking."
            )
    else:
        occurrences = [(payload.start_time, payload.end_time)]

    # Each conflict check is its own DB round-trip — for a long recurring
    # series (up to MAX_RECURRING_OCCURRENCES) that's a lot of them, so run
    # them concurrently rather than one at a time.
    checks = [(room, start, end) for room in rooms for start, end in occurrences]
    is_free = await asyncio.gather(*(_is_room_free(str(room["_id"]), start, end) for room, start, end in checks))
    busy_days: dict = {}
    for (room, start, _), free in zip(checks, is_free):
        if not free:
            busy_days.setdefault(room["name"], []).append(format_day(to_local(start)))
    if busy_days:
        raise HTTPException(
            409,
            "; ".join(f"{name} is already booked on: {', '.join(days)}" for name, days in busy_days.items())
            + " — nothing was created.",
        )

    series_id = uuid4().hex if len(occurrences) > 1 else None
    now = datetime.utcnow()
    base_fields = payload.model_dump(exclude={"recurrence", "start_time", "end_time", "room_id", "room_ids"})
    docs = []
    for start, end in occurrences:
        group_id = uuid4().hex if len(rooms) > 1 else None
        for room in rooms:
            docs.append(
                {
                    **base_fields,
                    "room_id": str(room["_id"]),
                    "start_time": start,
                    "end_time": end,
                    "room_name": room["name"],
                    "status": BookingStatus.approved.value,
                    "admin_note": None,
                    "series_id": series_id,
                    "group_id": group_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    result = await bookings_collection.insert_many(docs)
    # We already have every field of every created doc in `docs` — no need
    # to read them back from the DB one at a time, we just have to attach
    # the ids Mongo assigned.
    created_docs = [{**doc, "_id": _id} for doc, _id in zip(docs, result.inserted_ids)]

    # One confirmation for the event (not one per room), naming every room.
    combined = _combined_room(rooms)
    first = {**created_docs[0], "room_name": combined["name"]}
    background_tasks.add_task(notify_booking_confirmed, first, combined)
    for room in rooms:
        mine = [d for d in created_docs if d["room_id"] == str(room["_id"])]
        background_tasks.add_task(calendar_sync.sync_created_many, mine, room["name"])

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


@router.put("/calendar-events/rooms")
async def set_calendar_event_rooms(payload: EventRoomsUpdate, admin=Depends(get_current_admin)):
    """
    Choose which rooms a church-calendar event occupies. Saved against the
    event's UID, so a repeating event is set once for every date. An empty list
    clears it. Nothing already booked is cancelled — any existing bookings that
    now overlap the event are returned as `clashes` for the admin to sort out.
    """
    room_ids = list(dict.fromkeys(payload.room_ids))  # de-duplicate, keep order
    for room_id in room_ids:
        found = await rooms_collection.find_one({"_id": ObjectId(room_id)}) if ObjectId.is_valid(room_id) else None
        if not found or not found.get("active", True):
            raise HTTPException(404, "One of those rooms wasn't found")

    if room_ids:
        await event_rooms_collection.update_one(
            {"uid": payload.uid},
            {"$set": {"uid": payload.uid, "title": payload.title, "room_ids": room_ids, "updated_at": datetime.utcnow()}},
            upsert=True,
        )
    else:
        await event_rooms_collection.delete_one({"uid": payload.uid})

    return {
        "uid": payload.uid,
        "room_ids": room_ids,
        "clashes": await church_events.clashes(payload.uid, room_ids),
    }


@router.delete("/bookings/{booking_id}")
async def admin_delete_booking(booking_id: str, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")
    await bookings_collection.delete_one({"_id": ObjectId(booking_id)})
    background_tasks.add_task(calendar_sync.sync_removed, booking)
    return {"ok": True}


async def _cancel_all_where(field: str, value: str, background_tasks: BackgroundTasks) -> dict:
    live = {"$nin": [BookingStatus.cancelled.value, BookingStatus.rejected.value]}
    # Snapshot which bookings had a synced Google event *before* the bulk
    # update, since that's the only place their google_event_id is visible.
    to_unsync = [
        b async for b in bookings_collection.find({field: value, "status": live, "google_event_id": {"$ne": None}})
    ]
    result = await bookings_collection.update_many(
        {field: value, "status": live},
        {"$set": {"status": BookingStatus.cancelled.value, "updated_at": datetime.utcnow()}},
    )
    background_tasks.add_task(calendar_sync.sync_removed_many, to_unsync)
    return {"cancelled_count": result.modified_count}


@router.post("/bookings/series/{series_id}/cancel")
async def admin_cancel_series(series_id: str, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    return await _cancel_all_where("series_id", series_id, background_tasks)


@router.post("/bookings/group/{group_id}/cancel")
async def admin_cancel_group(group_id: str, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    """Cancels every room of one multi-room event (that date only, for a repeating series)."""
    return await _cancel_all_where("group_id", group_id, background_tasks)


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
    this_week = {"status": BookingStatus.approved.value, "start_time": {"$gte": now, "$lte": week_end}}

    async def _count_this_week():
        # A multi-room event is one booking: count single-room ones plus each group once.
        singles = await bookings_collection.count_documents({**this_week, "group_id": None})
        groups = await bookings_collection.distinct("group_id", this_week)
        return singles + len([g for g in groups if g])

    pending_count, upcoming_week_count, total_rooms, upcoming = await asyncio.gather(
        bookings_collection.count_documents({"status": BookingStatus.pending.value}),
        _count_this_week(),
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
    counted_groups: set = set()

    async for b in bookings_collection.find(
        {
            "created_at": {"$gte": window_start},
            "status": {"$nin": [BookingStatus.cancelled.value, BookingStatus.rejected.value]},
        }
    ):
        # Room use counts every room; demand (who/why/when) counts a multi-room
        # event once, however many rooms it took.
        by_room[b["room_name"]] += 1
        if b.get("group_id"):
            if b["group_id"] in counted_groups:
                continue
            counted_groups.add(b["group_id"])
        by_congregation[b["congregation"]] += 1
        by_purpose[b.get("purpose") or "Other"] += 1
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
