from datetime import datetime, timedelta
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

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
    AdminCreate,
    AdminLogin,
    AdminOut,
    Booking,
    BookingAdminAction,
    BookingStatus,
    Token,
)
from app.notifications import notify_booking_decision
from app.rate_limit import limiter
from app.routers.bookings import _booking_out

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
async def approve_booking(booking_id: str, action: BookingAdminAction, admin=Depends(get_current_admin)):
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
    await notify_booking_decision(updated, room, approved=True)
    return _booking_out(updated)


@router.post("/bookings/{booking_id}/reject", response_model=Booking)
async def reject_booking(booking_id: str, action: BookingAdminAction, admin=Depends(get_current_admin)):
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
    await notify_booking_decision(updated, room, approved=False)
    return _booking_out(updated)


@router.get("/dashboard")
async def dashboard_stats(admin=Depends(get_current_admin)):
    now = datetime.utcnow()
    week_end = now + timedelta(days=7)

    pending_count = await bookings_collection.count_documents({"status": BookingStatus.pending.value})
    upcoming_week_count = await bookings_collection.count_documents(
        {
            "status": BookingStatus.approved.value,
            "start_time": {"$gte": now, "$lte": week_end},
        }
    )
    total_rooms = await rooms_collection.count_documents({"active": True})

    upcoming = [
        _booking_out(b)
        async for b in bookings_collection.find(
            {"status": BookingStatus.approved.value, "start_time": {"$gte": now}}
        )
        .sort("start_time", 1)
        .limit(10)
    ]

    return {
        "pending_approvals": pending_count,
        "bookings_this_week": upcoming_week_count,
        "active_rooms": total_rooms,
        "next_bookings": upcoming,
    }
