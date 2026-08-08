from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_admin
from app.database import booking_purposes_collection
from app.models import BookingPurpose, BookingPurposeCreate, BookingPurposeUpdate

router = APIRouter(prefix="/api/booking-purposes", tags=["booking-purposes"])


def _purpose_out(doc: dict) -> BookingPurpose:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return BookingPurpose(**doc)


@router.get("", response_model=List[BookingPurpose])
async def list_purposes(active_only: bool = True):
    query = {"active": True} if active_only else {}
    purposes = [_purpose_out(p) async for p in booking_purposes_collection.find(query).sort("name", 1)]
    return purposes


@router.post("", response_model=BookingPurpose)
async def create_purpose(payload: BookingPurposeCreate, admin=Depends(get_current_admin)):
    existing = await booking_purposes_collection.find_one({"name": payload.name})
    if existing:
        raise HTTPException(400, "A purpose with this name already exists")
    result = await booking_purposes_collection.insert_one(payload.model_dump())
    created = await booking_purposes_collection.find_one({"_id": result.inserted_id})
    return _purpose_out(created)


@router.patch("/{purpose_id}", response_model=BookingPurpose)
async def update_purpose(
    purpose_id: str, payload: BookingPurposeUpdate, admin=Depends(get_current_admin)
):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update_data:
        await booking_purposes_collection.update_one(
            {"_id": ObjectId(purpose_id)}, {"$set": update_data}
        )
    updated = await booking_purposes_collection.find_one({"_id": ObjectId(purpose_id)})
    if not updated:
        raise HTTPException(404, "Purpose not found")
    return _purpose_out(updated)


@router.delete("/{purpose_id}")
async def deactivate_purpose(purpose_id: str, admin=Depends(get_current_admin)):
    await booking_purposes_collection.update_one(
        {"_id": ObjectId(purpose_id)}, {"$set": {"active": False}}
    )
    return {"ok": True}
