from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


def now_iso() -> datetime:
    return datetime.utcnow()


def _to_naive_utc(v: datetime) -> datetime:
    """
    Browsers send timezone-aware ISO timestamps (Date.toISOString() ends in
    "Z"), but the rest of the app compares against naive datetime.utcnow()
    and MongoDB stores/returns naive datetimes. Normalize on the way in so
    every start_time/end_time in the system is naive UTC.
    """
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class RoomType(str, Enum):
    classroom = "classroom"
    training_hall = "training_hall"
    main_hall = "main_hall"
    coffee_shop = "coffee_shop"
    lounge = "lounge"
    leap = "leap"


class BookingStatus(str, Enum):
    pending = "pending"          # awaiting admin approval
    approved = "approved"        # confirmed (auto or manual)
    rejected = "rejected"
    cancelled = "cancelled"


# ---------- Rooms ----------

class RoomBase(BaseModel):
    name: str
    type: RoomType
    capacity: int
    location: Optional[str] = None
    description: Optional[str] = Field(
        default=None,
        description="What's in the room and what the booker needs to bring, e.g. 'Chairs, sound system, projector. Bring your own markers.'",
    )
    setup_notes: Optional[str] = Field(
        default=None,
        description="What this room should look like when booking is done, e.g. 'Chairs stacked against back wall, tables wiped, projector off'",
    )
    photo_url: Optional[str] = None
    active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[RoomType] = None
    capacity: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    setup_notes: Optional[str] = None
    photo_url: Optional[str] = None
    active: Optional[bool] = None


class Room(RoomBase):
    id: str


# ---------- Congregations ----------

class CongregationBase(BaseModel):
    name: str
    active: bool = True


class CongregationCreate(CongregationBase):
    pass


class CongregationUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


class Congregation(CongregationBase):
    id: str


# ---------- Booking purposes ----------

class BookingPurposeBase(BaseModel):
    name: str
    active: bool = True


class BookingPurposeCreate(BookingPurposeBase):
    pass


class BookingPurposeUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


class BookingPurpose(BookingPurposeBase):
    id: str


# ---------- Bookings ----------

class BookingCreate(BaseModel):
    room_id: str
    requester_name: str
    congregation: str
    email: EmailStr
    phone: str
    headcount: int
    start_time: datetime
    end_time: datetime
    purpose: str
    purpose_other: Optional[str] = Field(
        default=None,
        description="Free-text detail when purpose is 'Other'",
    )
    is_private_event: bool = Field(
        default=False,
        description="Weddings, funerals, and other private (non-congregation) events always require admin approval",
    )
    notes: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalize_start_end(cls, v: datetime) -> datetime:
        return _to_naive_utc(v)


class BookingAdminAction(BaseModel):
    admin_note: Optional[str] = None


class RecurrenceFrequency(str, Enum):
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class RecurrenceRule(BaseModel):
    frequency: RecurrenceFrequency
    until: datetime

    @field_validator("until")
    @classmethod
    def _normalize_until(cls, v: datetime) -> datetime:
        return _to_naive_utc(v)


class AdminBookingCreate(BaseModel):
    room_id: str
    requester_name: str
    congregation: str
    email: EmailStr
    phone: str
    headcount: int
    start_time: datetime
    end_time: datetime
    purpose: str
    purpose_other: Optional[str] = None
    is_private_event: bool = False
    notes: Optional[str] = None
    recurrence: Optional[RecurrenceRule] = Field(
        default=None,
        description="If set, one booking is created per occurrence, sharing a series_id",
    )

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalize_start_end(cls, v: datetime) -> datetime:
        return _to_naive_utc(v)


class Booking(BaseModel):
    id: str
    room_id: str
    room_name: str
    requester_name: str
    congregation: str
    email: EmailStr
    phone: str
    headcount: int
    start_time: datetime
    end_time: datetime
    purpose: str
    purpose_other: Optional[str] = None
    is_private_event: bool
    notes: Optional[str] = None
    status: BookingStatus
    admin_note: Optional[str] = None
    series_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("start_time", "end_time", "created_at", "updated_at")
    def _serialize_as_utc(self, v: datetime) -> str:
        """
        Stored/compared as naive UTC internally, but the wire format must say
        so explicitly — otherwise `new Date(...)` on the frontend interprets
        the timezone-less string as local time instead of UTC.
        """
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


# ---------- Admin ----------

class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    setup_secret: Optional[str] = Field(
        default=None,
        description="Required only to create the first admin account; ignored once an admin already exists",
    )


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    id: str
    name: str
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminOut


# ---------- Room suggestions ----------

class RoomSuggestionRequest(BaseModel):
    headcount: int
    start_time: datetime
    end_time: datetime
    type: Optional[RoomType] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalize_start_end(cls, v: datetime) -> datetime:
        return _to_naive_utc(v)


class RoomSuggestion(BaseModel):
    room: Room
    available: bool
    fit_quality: str  # "good_fit" | "oversized" | "too_small"
