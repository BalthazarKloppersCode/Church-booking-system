from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pymongo import ReturnDocument

from app import notifications, password_reset
from app.auth import create_user_access_token, hash_password, verify_password
from app.database import users_collection
from app.models import ForgotPasswordRequest, ResetPasswordRequest, UserLogin, UserOut, UserToken
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


@router.post("/forgot-password")
@limiter.limit("10/hour")
async def forgot_password(request: Request, payload: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    """
    Sends a reset code to the WhatsApp number saved on the account. The reply is
    the same whether or not the email is registered (or the code was held back by
    the resend limits), so it can't be used to discover who has an account.
    """
    user = await users_collection.find_one({"email": payload.email})
    if user and user.get("active", True) and (user.get("phone") or "").strip():
        now = datetime.utcnow()
        sent = [t for t in (user.get("password_reset") or {}).get("sent_at", []) if now - t < timedelta(hours=1)]
        cooling_down = bool(sent) and now - max(sent) < password_reset.RESEND_COOLDOWN
        if not cooling_down and len(sent) < password_reset.MAX_CODES_PER_HOUR:
            code = password_reset.new_code()
            await users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "password_reset": {
                            "code_hash": password_reset.hash_code(user["email"], code),
                            "expires_at": now + password_reset.CODE_TTL,
                            "attempts": 0,
                            "sent_at": sent + [now],
                        }
                    }
                },
            )
            background_tasks.add_task(notifications.send_whatsapp, user["phone"], "password_reset", [code])
    return {"ok": True, "message": password_reset.GENERIC_REPLY}


@router.post("/reset-password")
@limiter.limit("20/hour")
async def reset_password(request: Request, payload: ResetPasswordRequest):
    """Sets a new password when given the code sent by /forgot-password. The code works once."""
    wrong = HTTPException(400, "That code is wrong or has expired — ask for a new one.")
    user = await users_collection.find_one({"email": payload.email})
    state = (user or {}).get("password_reset")
    if not user or not state or state["expires_at"] < datetime.utcnow():
        raise wrong

    # Count the guess first, atomically, so parallel requests can't squeeze in
    # extra tries past the limit.
    counted = await users_collection.find_one_and_update(
        {"_id": user["_id"], "password_reset.attempts": {"$lt": password_reset.MAX_ATTEMPTS}},
        {"$inc": {"password_reset.attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not counted or not password_reset.code_matches(user["email"], payload.code, counted["password_reset"]["code_hash"]):
        raise wrong

    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password_hash": hash_password(payload.new_password), "password_changed_at": datetime.utcnow()},
            "$unset": {"password_reset": ""},
        },
    )
    return {"ok": True}
