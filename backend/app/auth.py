from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.database import admins_collection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/admin/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(admin_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": admin_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


async def _decode_admin_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        admin_id: Optional[str] = payload.get("sub")
        if admin_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from bson import ObjectId
    admin = await admins_collection.find_one({"_id": ObjectId(admin_id)})
    if admin is None:
        raise credentials_exception
    return admin


async def get_current_admin(token: str = Depends(oauth2_scheme)) -> dict:
    return await _decode_admin_token(token)


async def get_current_admin_optional(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[dict]:
    """Like get_current_admin, but returns None instead of raising when no/invalid token is given."""
    if not token:
        return None
    try:
        return await _decode_admin_token(token)
    except HTTPException:
        return None
