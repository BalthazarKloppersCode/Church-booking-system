from fastapi import APIRouter, HTTPException, Request

from app.auth import create_user_access_token, verify_password
from app.database import users_collection
from app.models import UserLogin, UserOut, UserToken
from app.rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserToken)
@limiter.limit("10/minute")
async def login(request: Request, payload: UserLogin):
    user = await users_collection.find_one({"email": payload.email})
    if not user or not user.get("active", True) or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    token = create_user_access_token(str(user["_id"]))
    user_out = UserOut(id=str(user["_id"]), name=user["name"], email=user["email"], phone=user["phone"], active=user["active"])
    return UserToken(access_token=token, user=user_out)
