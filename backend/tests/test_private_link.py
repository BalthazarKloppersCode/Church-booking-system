from datetime import datetime, timedelta

import pytest

from app import notifications
from app.config import settings
from tests.conftest import make_room
from tests.test_calendar_sync import _make_admin

URL = "/api/public/private-events"


def body(room_id, days=30, hours=4, **overrides):
    start = (datetime.utcnow() + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    data = {
        "room_id": room_id,
        "requester_name": "Thandi Nkosi",
        "email": "thandi@example.com",
        "phone": "+27 82 123 4567",
        "congregation": "Durbanville",
        "headcount": 80,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=hours)).isoformat(),
        "purpose": "Wedding",
        "accepted_conditions": True,
    }
    data.update(overrides)
    return data


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def pending(booking, room):
        calls.append(("pending", booking["email"], room["name"]))

    async def admin_alert(booking, room):
        calls.append(("admin", booking["requester_name"], room["name"]))

    from app.routers import public_requests

    monkeypatch.setattr(public_requests, "notify_booking_pending", pending)
    monkeypatch.setattr(public_requests, "notify_admin_new_request", admin_alert)
    return calls


async def test_a_request_needs_no_login_and_always_waits_for_the_office(client, rooms_col, bookings_col, sent):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    resp = await client.post(URL, json=body(hall))
    assert resp.status_code == 200, resp.text
    made = resp.json()
    assert made["status"] == "pending" and made["is_private_event"] is True and made["source"] == "private_link"
    assert made["room_name"] == "Main Hall" and made["purpose"] == "Wedding"

    stored = await bookings_col.find_one({})
    assert stored["status"] == "pending" and stored["accepted_conditions"] is True and stored["source"] == "private_link"
    assert sent == [("pending", "thandi@example.com", "Main Hall"), ("admin", "Thandi Nkosi", "Main Hall")]


async def test_even_a_date_next_week_is_never_confirmed_on_its_own(client, rooms_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    resp = await client.post(URL, json=body(hall, days=3))
    assert resp.status_code == 200 and resp.json()["status"] == "pending"


async def test_the_caller_cannot_choose_the_status_or_skip_privacy(client, rooms_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    resp = await client.post(URL, json=body(hall, status="approved", is_private_event=False, source="admin"))
    assert resp.status_code == 200
    made = resp.json()
    assert made["status"] == "pending" and made["is_private_event"] is True and made["source"] == "private_link"


async def test_the_conditions_must_be_accepted(client, rooms_col, bookings_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    resp = await client.post(URL, json=body(hall, accepted_conditions=False))
    assert resp.status_code == 400 and "conditions" in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 0


async def test_the_hidden_field_catches_bots(client, rooms_col, bookings_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    resp = await client.post(URL, json=body(hall, website="http://spam.example"))
    assert resp.status_code == 400
    assert await bookings_col.count_documents({}) == 0 and sent == []


async def test_only_private_event_purposes_are_accepted(client, rooms_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    assert (await client.post(URL, json=body(hall, purpose="Bible study"))).status_code == 422
    assert (await client.post(URL, json=body(hall, purpose="Other"))).status_code == 422  # must describe it
    assert (await client.post(URL, json=body(hall, purpose="Other", purpose_other="Baby shower"))).status_code == 200


async def test_it_can_be_switched_off(client, rooms_col, bookings_col, sent, monkeypatch):
    hall = await make_room(rooms_col, capacity=300)
    monkeypatch.setattr(settings, "private_event_link_enabled", False)
    assert (await client.get(URL + "/status")).json()["enabled"] is False
    resp = await client.post(URL, json=body(hall))
    assert resp.status_code == 403 and "switched off" in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 0


async def test_dates_must_be_sensible(client, rooms_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    assert (await client.post(URL, json=body(hall, days=-2))).status_code == 400  # in the past
    assert (await client.post(URL, json=body(hall, days=900))).status_code == 400  # too far ahead
    assert (await client.post(URL, json=body(hall, hours=30))).status_code == 400  # longer than a day
    swapped = body(hall)
    swapped["start_time"], swapped["end_time"] = swapped["end_time"], swapped["start_time"]
    assert (await client.post(URL, json=swapped)).status_code == 400


async def test_room_and_headcount_are_checked(client, rooms_col, sent):
    small = await make_room(rooms_col, name="Small", capacity=20)
    gone = await make_room(rooms_col, name="Retired", capacity=300, active=False)
    assert (await client.post(URL, json=body(small, headcount=80))).status_code == 400
    assert (await client.post(URL, json=body(gone))).status_code == 404
    assert (await client.post(URL, json=body("not-an-id"))).status_code == 404
    assert (await client.post(URL, json=body("64b000000000000000000000"))).status_code == 404


async def test_a_room_that_is_already_taken_is_refused(client, rooms_col, bookings_col, sent):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    first = body(hall)
    assert (await client.post(URL, json=first)).status_code == 200
    clash = body(hall, email="other@example.com", phone="+27 83 000 0000", start_time=first["start_time"], end_time=first["end_time"])
    resp = await client.post(URL, json=clash)
    assert resp.status_code == 409
    assert await bookings_col.count_documents({}) == 1


async def test_one_person_cannot_hold_more_than_a_few_requests_at_once(client, rooms_col, bookings_col, sent):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    for day in (30, 40, 50):
        assert (await client.post(URL, json=body(hall, days=day))).status_code == 200
    again = await client.post(URL, json=body(hall, days=60))
    assert again.status_code == 429 and "waiting for the office" in again.json()["detail"]

    # The same phone number under a different email counts as the same person...
    assert (await client.post(URL, json=body(hall, days=61, email="alias@example.com"))).status_code == 429
    # ...and the email in a different case does too.
    assert (await client.post(URL, json=body(hall, days=62, email="THANDI@example.com", phone="+27 99 999 9999"))).status_code == 429
    # A different person is not affected.
    other = body(hall, days=63, email="sipho@example.com", phone="+27 84 555 5555", requester_name="Sipho")
    assert (await client.post(URL, json=other)).status_code == 200

    # Once the office has answered, the person can ask again.
    await bookings_col.update_many({"email": "thandi@example.com"}, {"$set": {"status": "rejected"}})
    assert (await client.post(URL, json=body(hall, days=64))).status_code == 200


async def test_the_requester_can_open_their_confirmation_but_the_office_sees_where_it_came_from(client, rooms_col, sent):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    made = (await client.post(URL, json=body(hall))).json()

    conf = await client.get(f"/api/bookings/{made['id']}/confirmation", params={"email": "thandi@example.com"})
    assert conf.status_code == 200 and conf.json()["status"] == "pending"
    assert (await client.get(f"/api/bookings/{made['id']}/confirmation", params={"email": "stranger@example.com"})).status_code == 403

    admin = await _make_admin(client)
    waiting = (await client.get("/api/admin/approvals", headers=admin)).json()
    assert [b["source"] for b in waiting] == ["private_link"]


async def test_the_office_can_approve_a_request_from_the_link(client, rooms_col, sent):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    made = (await client.post(URL, json=body(hall))).json()
    admin = await _make_admin(client)
    resp = await client.post(f"/api/admin/bookings/{made['id']}/approve", json={}, headers=admin)
    assert resp.status_code == 200 and resp.json()["status"] == "approved"


async def test_input_is_trimmed_and_limited(client, rooms_col, bookings_col, sent):
    hall = await make_room(rooms_col, capacity=300)
    assert (await client.post(URL, json=body(hall, notes="x" * 1001))).status_code == 422
    assert (await client.post(URL, json=body(hall, requester_name=""))).status_code == 422
    assert (await client.post(URL, json=body(hall, headcount=0))).status_code == 422
    assert (await client.post(URL, json=body(hall, email="not-an-email"))).status_code == 422
    ok = await client.post(URL, json=body(hall, requester_name="  Thandi  ", congregation="  "))
    assert ok.status_code == 200
    stored = await bookings_col.find_one({})
    assert stored["requester_name"] == "Thandi" and stored["congregation"] == "Private event request"
