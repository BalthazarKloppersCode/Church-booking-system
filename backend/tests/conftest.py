from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient


@pytest_asyncio.fixture
async def app_state(monkeypatch):
    """
    Points every router at the same in-memory mongomock database instead of
    a real MongoDB, and resets rate-limit state between tests so limits set
    for production traffic don't bleed across test cases.
    """
    from app import auth as auth_module
    from app import database as db_module
    from app.config import settings
    from app.rate_limit import limiter
    from app.routers import admin as admin_router
    from app.routers import areas as areas_router
    from app.routers import auth as booker_auth_router
    from app.routers import bookings as bookings_router
    from app.routers import congregations as congregations_router
    from app.routers import rooms as rooms_router
    from app.routers import users as users_router

    mock_db = AsyncMongoMockClient()["church_booking_test"]
    rooms_col = mock_db["rooms"]
    bookings_col = mock_db["bookings"]
    admins_col = mock_db["admins"]
    congregations_col = mock_db["congregations"]
    areas_col = mock_db["areas"]
    users_col = mock_db["users"]

    modules = (
        db_module,
        rooms_router,
        bookings_router,
        admin_router,
        auth_module,
        congregations_router,
        areas_router,
        users_router,
        booker_auth_router,
    )
    for module in modules:
        if hasattr(module, "rooms_collection"):
            monkeypatch.setattr(module, "rooms_collection", rooms_col)
        if hasattr(module, "bookings_collection"):
            monkeypatch.setattr(module, "bookings_collection", bookings_col)
        if hasattr(module, "admins_collection"):
            monkeypatch.setattr(module, "admins_collection", admins_col)
        if hasattr(module, "congregations_collection"):
            monkeypatch.setattr(module, "congregations_collection", congregations_col)
        if hasattr(module, "areas_collection"):
            monkeypatch.setattr(module, "areas_collection", areas_col)
        if hasattr(module, "users_collection"):
            monkeypatch.setattr(module, "users_collection", users_col)

    monkeypatch.setattr(settings, "admin_setup_secret", "test-setup-secret")
    monkeypatch.setattr(settings, "auto_approve_window_days", 14)

    limiter.reset()

    return {
        "rooms": rooms_col,
        "bookings": bookings_col,
        "admins": admins_col,
        "congregations": congregations_col,
        "areas": areas_col,
        "users": users_col,
    }


@pytest_asyncio.fixture
async def client(app_state):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def rooms_col(app_state):
    return app_state["rooms"]


@pytest_asyncio.fixture
async def bookings_col(app_state):
    return app_state["bookings"]


@pytest_asyncio.fixture
async def admins_col(app_state):
    return app_state["admins"]


@pytest_asyncio.fixture
async def congregations_col(app_state):
    return app_state["congregations"]


@pytest_asyncio.fixture
async def booker_headers(app_state):
    """
    Auth header for a registered booker. Inserts the user doc directly
    (like make_room does for rooms) instead of going through the admin
    register-a-user API, so this doesn't collide with tests that also
    bootstrap their own admin via the "first admin" setup-secret flow.
    """
    from app.auth import create_user_access_token

    result = await app_state["users"].insert_one({
        "name": "Booker",
        "email": "booker@example.com",
        "phone": "+10000000000",
        "active": True,
        "password_hash": "unused",
    })
    token = create_user_access_token(str(result.inserted_id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auto_approve_congregation(app_state):
    """
    A congregation in an area that has opted OUT of always-requiring
    approval (like Northern Hub) — the only kind of congregation where the
    2-week auto-approve window actually applies. Returns the congregation
    name to pass as `congregation` in a booking payload.
    """
    area = await app_state["areas"].insert_one({
        "name": "Northern Hub",
        "always_requires_approval": False,
        "active": True,
    })
    await app_state["congregations"].insert_one({
        "name": "Durbanville AM",
        "area_id": str(area.inserted_id),
        "active": True,
    })
    return "Durbanville AM"


async def make_room(rooms_col, **overrides):
    doc = {
        "name": "Room A",
        "type": "classroom",
        "capacity": 20,
        "location": None,
        "setup_notes": "Chairs stacked, tables wiped",
        "photo_url": None,
        "active": True,
    }
    doc.update(overrides)
    result = await rooms_col.insert_one(doc)
    return str(result.inserted_id)


def booking_payload(room_id, start_offset_days=5, duration_hours=2, **overrides):
    """
    start_offset_days is relative to "now" (the real system clock), matching
    how create_booking computes the auto-approval window off datetime.utcnow().
    """
    start = datetime.utcnow() + timedelta(days=start_offset_days)
    end = start + timedelta(hours=duration_hours)
    payload = {
        "room_id": room_id,
        "requester_name": "Jane Doe",
        "congregation": "Youth Group",
        "email": "jane@example.com",
        "phone": "+10000000000",
        "headcount": 10,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "purpose": "Bible study",
        "is_private_event": False,
    }
    payload.update(overrides)
    return payload
