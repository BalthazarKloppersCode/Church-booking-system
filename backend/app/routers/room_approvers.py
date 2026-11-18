"""
Which WhatsApp numbers are alerted when a booking for a given room needs approval (admin only).

The numbers live on the room document but are deliberately not part of the public Room model, so
they never appear in GET /api/rooms. A room with no numbers falls back to ADMIN_NOTIFY_WHATSAPP.
"""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import whatsapp
from app.auth import get_current_admin
from app.database import rooms_collection

router = APIRouter(prefix="/api/admin/room-approvers", tags=["room-approvers"])

MAX_NUMBERS = 10


class ApproverNumbers(BaseModel):
    numbers: list[str] = Field(default_factory=list, max_length=50)


def clean_numbers(raw: list[str]) -> list[str]:
    """'+digits' for each valid, distinct number; raises ValueError naming the first bad one."""
    seen: list[str] = []
    for item in raw:
        if not item.strip():
            continue
        digits = whatsapp.normalize_phone(item)
        if not digits:
            raise ValueError(f"“{item.strip()[:40]}” doesn't look like a phone number.")
        if digits not in seen:
            seen.append(digits)
    if len(seen) > MAX_NUMBERS:
        raise ValueError(f"At most {MAX_NUMBERS} numbers per room.")
    return [f"+{d}" for d in seen]


@router.get("")
async def list_approvers(admin=Depends(get_current_admin)):
    result = {}
    async for room in rooms_collection.find({"active": {"$ne": False}}):
        if room.get("approval_whatsapp"):
            result[str(room["_id"])] = room["approval_whatsapp"]
    return result


@router.put("/{room_id}")
async def set_approvers(room_id: str, payload: ApproverNumbers, admin=Depends(get_current_admin)):
    if not ObjectId.is_valid(room_id) or not await rooms_collection.find_one({"_id": ObjectId(room_id)}):
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        numbers = clean_numbers(payload.numbers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if numbers:
        await rooms_collection.update_one({"_id": ObjectId(room_id)}, {"$set": {"approval_whatsapp": numbers}})
    else:
        await rooms_collection.update_one({"_id": ObjectId(room_id)}, {"$unset": {"approval_whatsapp": ""}})
    return {"room_id": room_id, "numbers": numbers}
