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

# Rooms of these types are exempt from the "oversized" size-block below —
# they're already the smallest category on campus, so there's never a
# smaller-but-sufficient alternative to steer someone toward.
SMALL_ROOM_TYPES = {"classroom", "leap"}

OVERSIZED_RATIO = 1.2  # more than 20% bigger than the best-fitting option = blocked


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
    existing = await rooms_collection.find_one({"_id": ObjectId(room_id)})
    if not existing:
        raise HTTPException(404, "Room not found")

    update_data = {k: v for k, v in room.model_dump().items() if v is not None}
    # Everywhere else null means "not provided", but for the minimum an explicit
    # null is how an admin clears it back to the automatic size rule.
    if "min_people" in room.model_fields_set and room.min_people is None:
        update_data["min_people"] = None

    new_capacity = update_data.get("capacity", existing["capacity"])
    new_min = update_data["min_people"] if "min_people" in update_data else existing.get("min_people")
    if new_min is not None and new_min > new_capacity:
        raise HTTPException(400, "The minimum number of people can't be more than the room's capacity")

    if update_data:
        await rooms_collection.update_one({"_id": ObjectId(room_id)}, {"$set": update_data})
    updated = await rooms_collection.find_one({"_id": ObjectId(room_id)})
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

    def below_minimum(room) -> bool:
        return room.get("min_people") is not None and req.headcount < room["min_people"]

    # The smallest capacity among rooms that actually fit the group — this is
    # the "right-sized" reference point. A room the group is under the
    # configured minimum for isn't a candidate, or it could pull the reference
    # down to a room nobody can book and block everything else as oversized. A non-classroom room is only blocked
    # as oversized if something closer to this reference exists; if the best
    # fit already IS a big room (e.g. the group is too large for any
    # classroom), that room stays selectable rather than everything getting
    # blocked and leaving nothing bookable.
    fitting_capacities = [
        room["capacity"]
        for room in candidates
        if room["capacity"] >= req.headcount and not below_minimum(room)
    ]
    best_fit_capacity = min(fitting_capacities) if fitting_capacities else None

    suggestions = []
    for room, free in zip(candidates, availability):
        room_out = _room_out(room)

        note = None
        if room["capacity"] < req.headcount:
            fit = "too_small"
        elif room.get("min_people") is not None:
            # An explicit range from Manage Rooms decides on its own: offered to
            # any group from min_people up to capacity, however much bigger than
            # the "best fit" it is.
            if below_minimum(room):
                fit = "oversized"
                note = f"Needs at least {room['min_people']} people"
            else:
                fit = "good_fit"
        elif room["type"] in SMALL_ROOM_TYPES:
            fit = "good_fit"
        elif best_fit_capacity is not None and room["capacity"] > best_fit_capacity * OVERSIZED_RATIO:
            fit = "oversized"
            note = "Too large for your group — pick a smaller room"
        else:
            fit = "good_fit"

        suggestions.append(RoomSuggestion(room=room_out, available=free, fit_quality=fit, note=note))

    return suggestions
