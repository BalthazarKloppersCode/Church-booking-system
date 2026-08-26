import asyncio
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import get_current_admin
from app.database import rooms_collection, bookings_collection
from app.models import Room, RoomCreate, RoomUpdate, RoomSuggestionRequest, RoomSuggestion
from app.rate_limit import limiter

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def _room_out(doc: dict) -> Room:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return Room(**doc)


@router.get("", response_model=List[Room])
async def list_rooms(active_only: bool = True):
    query = {"active": True} if active_only else {}
    rooms = [_room_out(r) async for r in rooms_collection.find(query).sort("capacity", 1)]
    return rooms


@router.post("", response_model=Room)
async def create_room(room: RoomCreate, admin=Depends(get_current_admin)):
    result = await rooms_collection.insert_one(room.model_dump())
    created = await rooms_collection.find_one({"_id": result.inserted_id})
    return _room_out(created)


@router.patch("/{room_id}", response_model=Room)
async def update_room(room_id: str, room: RoomUpdate, admin=Depends(get_current_admin)):
    update_data = {k: v for k, v in room.model_dump().items() if v is not None}
    if update_data:
        await rooms_collection.update_one({"_id": ObjectId(room_id)}, {"$set": update_data})
    updated = await rooms_collection.find_one({"_id": ObjectId(room_id)})
    if not updated:
        raise HTTPException(404, "Room not found")
    return _room_out(updated)


@router.delete("/{room_id}")
async def deactivate_room(room_id: str, admin=Depends(get_current_admin)):
    await rooms_collection.update_one({"_id": ObjectId(room_id)}, {"$set": {"active": False}})
    return {"ok": True}


async def _is_room_free(room_id: str, start: datetime, end: datetime) -> bool:
    overlap = await bookings_collection.find_one({
        "room_id": room_id,
        "status": {"$in": ["pending", "approved"]},
        "start_time": {"$lt": end},
        "end_time": {"$gt": start},
    })
    return overlap is None


@router.post("/suggest", response_model=List[RoomSuggestion])
@limiter.limit("30/minute")
async def suggest_rooms(request: Request, req: RoomSuggestionRequest):
    """
    Suggests rooms that fit the requested headcount, ranked by best fit
    (smallest room that still fits the group), and flags which are
    actually free for the requested time slot.
    """
    query = {"active": True, "capacity": {"$gte": req.headcount}}
    if req.type:
        query["type"] = req.type.value

    candidates = [r async for r in rooms_collection.find(query).sort("capacity", 1)]

    # If nothing fits exactly, fall back to the largest available rooms
    # (still useful — admin can decide) rather than returning nothing.
    if not candidates:
        fallback_query = {"active": True}
        if req.type:
            fallback_query["type"] = req.type.value
        candidates = [
            r async for r in rooms_collection.find(fallback_query).sort("capacity", -1)
        ][:3]

    # Each availability check is its own DB round-trip — run them concurrently
    # instead of one-by-one, since they're independent of each other.
    availability = await asyncio.gather(
        *(_is_room_free(str(room["_id"]), req.start_time, req.end_time) for room in candidates)
    )

    suggestions = []
    for room, free in zip(candidates, availability):
        room_out = _room_out(room)

        if room["capacity"] < req.headcount:
            fit = "too_small"
        elif room["capacity"] > req.headcount * 2 and room["capacity"] > 40:
            fit = "oversized"
        else:
            fit = "good_fit"

        suggestions.append(RoomSuggestion(room=room_out, available=free, fit_quality=fit))

    return suggestions
