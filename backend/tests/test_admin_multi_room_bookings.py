from datetime import datetime, timedelta

import pytest

from app.routers import admin as admin_router
from tests.conftest import make_room
from tests.test_calendar_sync import _make_admin


def payload(**overrides):
    start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=5)
    body = {
        "requester_name": "Office",
        "congregation": "Youth Group",
        "email": "office@example.com",
        "phone": "+27820000000",
        "headcount": 150,
        "purpose": "Training / workshop",
        "is_private_event": False,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=3)).isoformat(),
    }
    body.update(overrides)
    return body


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_notify(booking, room):
        calls.append((booking, room))

    monkeypatch.setattr(admin_router, "notify_booking_confirmed", fake_notify)
    return calls


async def test_one_event_can_take_several_rooms(client, rooms_col, bookings_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=100, amenities=["Sound system", "Chairs"], location="Ground floor")
    foyer = await make_room(rooms_col, name="Foyer", capacity=80, amenities=["Chairs", "TV & HDMI"], location="Ground floor")

    resp = await client.post("/api/admin/bookings", json=payload(room_ids=[hall, foyer]), headers=admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_count"] == 2
    made = body["bookings"]
    assert {b["room_name"] for b in made} == {"Main Hall", "Foyer"}
    assert {b["status"] for b in made} == {"approved"}
    assert made[0]["group_id"] and made[0]["group_id"] == made[1]["group_id"]
    assert made[0]["start_time"] == made[1]["start_time"]

    # One confirmation for the whole event, naming both rooms and pooling their equipment.
    assert len(sent) == 1
    booking, room = sent[0]
    assert room["name"] == "Main Hall and Foyer" == booking["room_name"]
    assert room["amenities"] == ["Sound system", "Chairs", "TV & HDMI"]
    assert room["location"] == "Ground floor"


async def test_the_old_single_room_request_still_works(client, rooms_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=200)
    resp = await client.post("/api/admin/bookings", json=payload(room_id=hall, headcount=50), headers=admin)
    assert resp.status_code == 200
    assert resp.json()["bookings"][0]["group_id"] is None
    assert sent[0][1]["name"] == "Main Hall"


async def test_the_headcount_only_has_to_fit_the_rooms_together(client, rooms_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=100)
    foyer = await make_room(rooms_col, name="Foyer", capacity=80)

    assert (await client.post("/api/admin/bookings", json=payload(room_ids=[hall, foyer], headcount=170), headers=admin)).status_code == 200
    tooMany = await client.post("/api/admin/bookings", json=payload(room_ids=[hall, foyer], headcount=181), headers=admin)
    assert tooMany.status_code == 400 and "180" in tooMany.json()["detail"]
    # A single room is still held to its own capacity.
    assert (await client.post("/api/admin/bookings", json=payload(room_ids=[foyer], headcount=90), headers=admin)).status_code == 400


async def test_one_busy_room_stops_the_whole_event_and_names_it(client, rooms_col, bookings_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=100)
    foyer = await make_room(rooms_col, name="Foyer", capacity=80)
    first = payload(room_id=foyer, headcount=20)
    assert (await client.post("/api/admin/bookings", json=first, headers=admin)).status_code == 200

    resp = await client.post("/api/admin/bookings", json=payload(room_ids=[hall, foyer], headcount=120), headers=admin)
    assert resp.status_code == 409
    assert "Foyer is already booked" in resp.json()["detail"] and "Main Hall" not in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 1  # nothing was created for the free room either


async def test_a_repeating_multi_room_event_gets_a_group_per_date(client, rooms_col, bookings_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=100)
    foyer = await make_room(rooms_col, name="Foyer", capacity=80)
    start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=5)
    body = payload(
        room_ids=[hall, foyer],
        recurrence={"frequency": "weekly", "until": (start + timedelta(days=15)).isoformat()},
    )
    resp = await client.post("/api/admin/bookings", json=body, headers=admin)
    assert resp.status_code == 200, resp.text
    made = resp.json()["bookings"]
    assert len(made) == 6  # 3 dates x 2 rooms
    assert len({b["series_id"] for b in made}) == 1
    assert len({b["group_id"] for b in made}) == 3
    assert len(sent) == 1  # a single confirmation, not six


async def test_cancelling_a_group_cancels_every_room_of_that_date_only(client, rooms_col, bookings_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=100)
    foyer = await make_room(rooms_col, name="Foyer", capacity=80)
    start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=5)
    body = payload(room_ids=[hall, foyer], recurrence={"frequency": "weekly", "until": (start + timedelta(days=8)).isoformat()})
    made = (await client.post("/api/admin/bookings", json=body, headers=admin)).json()["bookings"]
    first_group = made[0]["group_id"]

    resp = await client.post(f"/api/admin/bookings/group/{first_group}/cancel", headers=admin)
    assert resp.status_code == 200 and resp.json()["cancelled_count"] == 2
    statuses = {(b["group_id"] == first_group): b["status"] async for b in _all(bookings_col)}
    assert statuses == {True: "cancelled", False: "approved"}


async def _all(col):
    async for doc in col.find({}):
        yield {"group_id": doc.get("group_id"), "status": doc["status"]}


async def test_a_room_must_be_chosen_and_must_exist(client, rooms_col, sent):
    admin = await _make_admin(client)
    assert (await client.post("/api/admin/bookings", json=payload(), headers=admin)).status_code == 422
    assert (await client.post("/api/admin/bookings", json=payload(room_ids=[]), headers=admin)).status_code == 422
    resp = await client.post("/api/admin/bookings", json=payload(room_ids=["64b000000000000000000000"]), headers=admin)
    assert resp.status_code == 404
    assert (await client.post("/api/admin/bookings", json=payload(room_ids=["nope"]), headers=admin)).status_code == 404


async def test_duplicate_rooms_in_the_request_are_collapsed(client, rooms_col, sent):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=200)
    resp = await client.post("/api/admin/bookings", json=payload(room_ids=[hall, hall], headcount=50), headers=admin)
    assert resp.status_code == 200 and resp.json()["created_count"] == 1
    assert resp.json()["bookings"][0]["group_id"] is None


def test_combined_room_notes_are_labelled_only_when_they_differ():
    a = {"name": "Main Hall", "amenities": ["Chairs"], "location": None, "setup_notes": "Stack chairs", "booking_message": None}
    b = {"name": "Foyer", "amenities": ["Chairs", "TV & HDMI"], "location": None, "setup_notes": "Stack chairs", "booking_message": "Keys at the desk"}
    c = {"name": "Kitchen", "amenities": [], "location": "Rear", "setup_notes": "Wipe tables", "booking_message": None}

    same = admin_router._combined_room([a, b])
    assert same["name"] == "Main Hall and Foyer"
    assert same["setup_notes"] == "Stack chairs"  # identical -> not repeated per room
    assert same["booking_message"] == "Keys at the desk"  # only one room has one -> as is

    differ = admin_router._combined_room([a, b, c])
    assert differ["name"] == "Main Hall, Foyer and Kitchen"
    assert differ["setup_notes"] == "Main Hall: Stack chairs\nFoyer: Stack chairs\nKitchen: Wipe tables"
    assert differ["amenities"] == ["Chairs", "TV & HDMI"] and differ["location"] == "Rear"

    # And the real confirmation builds from it.
    from app.notifications import build_confirmation_email

    booking = {
        "_id": "65a1b2c3d4e5f60718293a4b", "requester_name": "Jane", "email": "j@example.com", "phone": "+27820000000",
        "purpose": "Training / workshop", "purpose_other": None, "is_private_event": False,
        "start_time": datetime(2026, 10, 18, 7), "end_time": datetime(2026, 10, 18, 9), "room_name": differ["name"],
    }
    _, text, _ = build_confirmation_email(booking, differ)
    assert "Main Hall, Foyer and Kitchen" in text and "Room equipment: Chairs, TV & HDMI" in text
