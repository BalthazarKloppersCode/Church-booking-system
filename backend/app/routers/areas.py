from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_admin
from app.database import areas_collection
from app.models import Area, AreaCreate, AreaUpdate

router = APIRouter(prefix="/api/areas", tags=["areas"])


def _area_out(doc: dict) -> Area:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return Area(**doc)


@router.get("", response_model=List[Area])
async def list_areas(active_only: bool = True):
    query = {"active": True} if active_only else {}
    areas = [_area_out(a) async for a in areas_collection.find(query).sort("name", 1)]
    return areas


@router.post("", response_model=Area)
async def create_area(payload: AreaCreate, admin=Depends(get_current_admin)):
    existing = await areas_collection.find_one({"name": payload.name})
    if existing:
        raise HTTPException(400, "An area with this name already exists")
    result = await areas_collection.insert_one(payload.model_dump())
    created = await areas_collection.find_one({"_id": result.inserted_id})
    return _area_out(created)


@router.patch("/{area_id}", response_model=Area)
async def update_area(area_id: str, payload: AreaUpdate, admin=Depends(get_current_admin)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update_data:
        await areas_collection.update_one({"_id": ObjectId(area_id)}, {"$set": update_data})
    updated = await areas_collection.find_one({"_id": ObjectId(area_id)})
    if not updated:
        raise HTTPException(404, "Area not found")
    return _area_out(updated)


@router.delete("/{area_id}")
async def deactivate_area(area_id: str, admin=Depends(get_current_admin)):
    await areas_collection.update_one({"_id": ObjectId(area_id)}, {"$set": {"active": False}})
    return {"ok": True}
