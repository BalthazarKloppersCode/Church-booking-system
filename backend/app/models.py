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
    barista = "barista"


class BookingStatus(str, Enum):
    pending = "pending"          # awaiting admin approval
    approved = "approved"        # confirmed (auto or manual)
    rejected = "rejected"
    cancelled = "cancelled"


# ---------- Rooms ----------

ROOM_AMENITIES = ["Microphone", "Sound system", "AV", "TV & HDMI", "Chairs"]


class RoomBase(BaseModel):
    name: str
    type: RoomType
    capacity: int
    location: Optional[str] = None
    amenities: List[str] = Field(
        default_factory=list,
        description=f"Subset of: {', '.join(ROOM_AMENITIES)}",
    )
    description: Optional[str] = Field(
        default=None,
        description="Anything else about the room not covered by the fixed amenities list",
    )
    setup_notes: Optional[str] = Field(
        default=None,
        description="What this room should look like when booking is done, e.g. 'Chairs stacked against back wall, tables wiped, projector off'",
    )
    booking_message: Optional[str] = Field(
        default=None,
        description="Custom message sent to bookers on confirmation — what to bring, condition to leave it in, what they're liable for",
    )
    photo_urls: List[str] = Field(
        default_factory=list,
        description="Pasted image URLs shown/linked in the booking confirmation",
    )
    photo_url: Optional[str] = None
    always_requires_approval: bool = Field(
        default=False,
        description=(
            "If true, bookings for this room always need admin approval, no matter how far out "
            "they are or which area the booker belongs to — e.g. Hebrews (the barista shop add-on)."
        ),
    )
    active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[RoomType] = None
    capacity: Optional[int] = None
    location: Optional[str] = None
    amenities: Optional[List[str]] = None
    description: Optional[str] = None
    setup_notes: Optional[str] = None
    booking_message: Optional[str] = None
    photo_urls: Optional[List[str]] = None
    photo_url: Optional[str] = None
    always_requires_approval: Optional[bool] = None
    active: Optional[bool] = None


class Room(RoomBase):
    id: str


# ---------- Areas ----------

class AreaBase(BaseModel):
    name: str
    always_requires_approval: bool = Field(
        default=True,
        description=(
            "Every booking now requires a logged-in user regardless of area. This flag is "
            "about timing instead: if true (the default), bookings for this area always need "
            "admin approval no matter how far out they are. Set false only for areas that "
            "should get the standard 2-week auto-approve window, e.g. Northern Hub."
        ),
    )
    active: bool = True


class AreaCreate(AreaBase):
    pass


class AreaUpdate(BaseModel):
    name: Optional[str] = None
    always_requires_approval: Optional[bool] = None
    active: Optional[bool] = None


class Area(AreaBase):
    id: str


# ---------- Congregations ----------

class CongregationBase(BaseModel):
    name: str
    area_id: str
    active: bool = True


class CongregationCreate(CongregationBase):
    pass


class CongregationUpdate(BaseModel):
    name: Optional[str] = None
    area_id: Optional[str] = None
    active: Optional[bool] = None


class Congregation(CongregationBase):
    id: str


# ---------- Booker users ----------

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    area_id: Optional[str] = Field(
        default=None,
        description=(
            "The area this user belongs to. Drives the auto-approve/needs-approval rule for "
            "bookings they make — set this to whichever area's login-required perk they should "
            "get (e.g. Northern Hub), not the congregation typed into the booking form."
        ),
    )
    active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    area_id: Optional[str] = None
    password: Optional[str] = None
    active: Optional[bool] = None


class UserOut(UserBase):
    id: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


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


class AdminBookingUpdate(BaseModel):
    room_id: Optional[str] = None
    requester_name: Optional[str] = None
    congregation: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    headcount: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    purpose: Optional[str] = None
    purpose_other: Optional[str] = None
    is_private_event: Optional[bool] = None
    notes: Optional[str] = None
    status: Optional[BookingStatus] = None
    admin_note: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalize_start_end(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _to_naive_utc(v) if v is not None else v


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


class CalendarEntry(BaseModel):
    """
    Privacy-safe booking overview for the public booker-facing calendar —
    just room/time/status, never requester name, congregation, email, or
    phone. Use the full `Booking` model (via an authenticated/admin route)
    for anything that needs the actual booking record.
    """
    room_name: str
    start_time: datetime
    end_time: datetime
    status: BookingStatus

    @field_serializer("start_time", "end_time")
    def _serialize_as_utc(self, v: datetime) -> str:
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
