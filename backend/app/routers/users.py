from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_admin, hash_password
from app.database import users_collection
from app.models import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/admin/users", tags=["users"])


def _user_out(doc: dict) -> UserOut:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    doc.pop("password_hash", None)
    return UserOut(**doc)


@router.get("", response_model=List[UserOut])
async def list_users(admin=Depends(get_current_admin)):
    return [_user_out(u) async for u in users_collection.find({}).sort("name", 1)]


@router.post("", response_model=UserOut)
async def create_user(payload: UserCreate, admin=Depends(get_current_admin)):
    existing = await users_collection.find_one({"email": payload.email})
    if existing:
        raise HTTPException(400, "A user with this email already exists")
    doc = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "area_id": payload.area_id,
        "active": payload.active,
        "password_hash": hash_password(payload.password),
    }
    result = await users_collection.insert_one(doc)
    created = await users_collection.find_one({"_id": result.inserted_id})
    return _user_out(created)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, payload: UserUpdate, admin=Depends(get_current_admin)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None and k != "password"}
    if payload.password:
        update_data["password_hash"] = hash_password(payload.password)
    if update_data:
        await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    updated = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not updated:
        raise HTTPException(404, "User not found")
    return _user_out(updated)


@router.delete("/{user_id}")
async def delete_user(user_id: str, admin=Depends(get_current_admin)):
    await users_collection.delete_one({"_id": ObjectId(user_id)})
    return {"ok": True}
