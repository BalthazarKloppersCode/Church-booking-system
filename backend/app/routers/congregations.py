from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_admin
from app.database import congregations_collection
from app.models import Congregation, CongregationCreate, CongregationUpdate

router = APIRouter(prefix="/api/congregations", tags=["congregations"])


def _congregation_out(doc: dict) -> Congregation:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return Congregation(**doc)


@router.get("", response_model=List[Congregation])
async def list_congregations(active_only: bool = True):
    query = {"active": True} if active_only else {}
    congregations = [
        _congregation_out(c) async for c in congregations_collection.find(query).sort("name", 1)
    ]
    return congregations


@router.post("", response_model=Congregation)
async def create_congregation(payload: CongregationCreate, admin=Depends(get_current_admin)):
    existing = await congregations_collection.find_one({"name": payload.name})
    if existing:
        raise HTTPException(400, "A congregation with this name already exists")
    result = await congregations_collection.insert_one(payload.model_dump())
    created = await congregations_collection.find_one({"_id": result.inserted_id})
    return _congregation_out(created)


@router.patch("/{congregation_id}", response_model=Congregation)
async def update_congregation(
    congregation_id: str, payload: CongregationUpdate, admin=Depends(get_current_admin)
):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update_data:
        await congregations_collection.update_one(
            {"_id": ObjectId(congregation_id)}, {"$set": update_data}
        )
    updated = await congregations_collection.find_one({"_id": ObjectId(congregation_id)})
    if not updated:
        raise HTTPException(404, "Congregation not found")
    return _congregation_out(updated)


@router.delete("/{congregation_id}")
async def deactivate_congregation(congregation_id: str, admin=Depends(get_current_admin)):
    await congregations_collection.update_one(
        {"_id": ObjectId(congregation_id)}, {"$set": {"active": False}}
    )
    return {"ok": True}
