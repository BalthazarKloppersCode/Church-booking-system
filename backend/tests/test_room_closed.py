from datetime import datetime, timedelta

from tests.conftest import booking_payload, make_room
from tests.test_calendar_sync import _make_admin

REASON = "Awaiting fire marshal approval"


async def close(client, admin, room_id, reason=REASON):
    resp = await client.patch(f"/api/rooms/{room_id}", json={"bookable": False, "closed_reason": reason}, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()


def window(days=5, hours=2):
    start = (datetime.utcnow() + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(hours=hours)).isoformat()}


async def test_an_admin_can_close_and_reopen_a_room(client, rooms_col):
    admin = await _make_admin(client)
    lounge = await make_room(rooms_col, name="Lounge")
    closed = await close(client, admin, lounge)
    assert closed["bookable"] is False and closed["closed_reason"] == REASON

    opened = await client.patch(f"/api/rooms/{lounge}", json={"bookable": True}, headers=admin)
    assert opened.json()["bookable"] is True and opened.json()["closed_reason"] is None


async def test_rooms_are_open_unless_closed(client, rooms_col):
    await make_room(rooms_col, name="Main Hall")
    listed = (await client.get("/api/rooms")).json()
    assert listed[0]["bookable"] is True and listed[0]["closed_reason"] is None


async def test_only_an_admin_can_close_a_room(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    assert (await client.patch(f"/api/rooms/{room}", json={"bookable": False})).status_code == 401
    assert (await client.patch(f"/api/rooms/{room}", json={"bookable": False}, headers=booker_headers)).status_code == 401


async def test_a_closed_room_cannot_be_booked_by_a_booker_and_says_why(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    leap = await make_room(rooms_col, name="Leap Classroom 1")
    await close(client, admin, leap)
    resp = await client.post("/api/bookings", json=booking_payload(leap), headers=booker_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"Leap Classroom 1 isn't open for booking yet: {REASON}"


async def test_a_closed_room_cannot_be_booked_by_the_office_either(client, rooms_col, bookings_col):
    admin = await _make_admin(client)
    kids = await make_room(rooms_col, name="Kids Classroom 3")
    fine = await make_room(rooms_col, name="Kids Classroom 1")
    await close(client, admin, kids)
    body = {"requester_name": "Office", "congregation": "Youth", "email": "o@example.com", "phone": "+2700000", "headcount": 5,
            "purpose": "Bible study", **window()}
    single = await client.post("/api/admin/bookings", json={**body, "room_id": kids}, headers=admin)
    assert single.status_code == 409 and "isn't open for booking yet" in single.json()["detail"]
    # One closed room stops a multi-room booking, and nothing is made for the open one.
    several = await client.post("/api/admin/bookings", json={**body, "room_ids": [fine, kids]}, headers=admin)
    assert several.status_code == 409 and "Kids Classroom 3" in several.json()["detail"]
    assert await bookings_col.count_documents({}) == 0


async def test_a_closed_room_cannot_be_requested_through_the_private_link(client, rooms_col, bookings_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Training Hall", capacity=200)
    await close(client, admin, hall)
    resp = await client.post(
        "/api/public/private-events",
        json={"room_id": hall, "requester_name": "Thandi", "email": "t@example.com", "phone": "+27 82 123 4567", "headcount": 50,
              "purpose": "Wedding", "accepted_conditions": True, **window(days=40)},
    )
    assert resp.status_code == 409 and "isn't open for booking yet" in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 0


async def test_the_office_cannot_move_a_booking_into_a_closed_room(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    open_room = await make_room(rooms_col, name="Open Room")
    shut = await make_room(rooms_col, name="Shut Room")
    made = (await client.post("/api/bookings", json=booking_payload(open_room), headers=booker_headers)).json()
    await close(client, admin, shut)
    moved = await client.patch(f"/api/admin/bookings/{made['id']}", json={"room_id": shut}, headers=admin)
    assert moved.status_code == 409


async def test_bookings_already_in_a_room_stand_when_it_is_closed(client, rooms_col, bookings_col, booker_headers):
    admin = await _make_admin(client)
    room = await make_room(rooms_col, name="Lounge")
    made = (await client.post("/api/bookings", json=booking_payload(room), headers=booker_headers)).json()
    await close(client, admin, room)
    stored = await bookings_col.find_one({})
    assert stored["status"] == made["status"] and stored["status"] in ("approved", "pending")
    listed = (await client.get("/api/bookings", params={"room_id": room}, headers=admin)).json()
    assert len(listed) == 1  # still there, so the office can see and move it


async def test_closing_a_room_does_not_affect_other_rooms(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    shut = await make_room(rooms_col, name="Shut")
    fine = await make_room(rooms_col, name="Fine")
    await close(client, admin, shut)
    assert (await client.post("/api/bookings", json=booking_payload(fine), headers=booker_headers)).status_code == 200


async def test_reopening_makes_it_bookable_again(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    room = await make_room(rooms_col, name="Leap Classroom 2")
    await close(client, admin, room)
    assert (await client.post("/api/bookings", json=booking_payload(room), headers=booker_headers)).status_code == 409
    await client.patch(f"/api/rooms/{room}", json={"bookable": True}, headers=admin)
    assert (await client.post("/api/bookings", json=booking_payload(room), headers=booker_headers)).status_code == 200


async def test_suggestions_show_a_closed_room_as_not_open_with_the_reason(client, rooms_col):
    admin = await _make_admin(client)
    open_room = await make_room(rooms_col, name="Open", capacity=40)
    shut = await make_room(rooms_col, name="Shut", capacity=40)
    await close(client, admin, shut)
    start = datetime.utcnow() + timedelta(days=5)
    resp = await client.post("/api/rooms/suggest", json={"headcount": 20, "start_time": start.isoformat(), "end_time": (start + timedelta(hours=2)).isoformat()})
    by_name = {s["room"]["name"]: s for s in resp.json()}
    assert by_name["Shut"]["closed"] is True and by_name["Shut"]["available"] is False and by_name["Shut"]["note"] == REASON
    assert by_name["Open"]["closed"] is False and by_name["Open"]["available"] is True


async def test_a_closed_room_does_not_distort_which_rooms_count_as_too_large(client, rooms_col):
    admin = await _make_admin(client)
    # Without the closed 30-seat hall, the 60-seat room is the best fit for 25 people and the
    # 200-seat room is "too large". A closed small room must not change that either way.
    small = await make_room(rooms_col, name="Closed small", type="classroom", capacity=30)
    await close(client, admin, small)
    mid = await make_room(rooms_col, name="Mid", type="training_hall", capacity=60)
    big = await make_room(rooms_col, name="Big", type="main_hall", capacity=200)
    start = datetime.utcnow() + timedelta(days=5)
    resp = await client.post("/api/rooms/suggest", json={"headcount": 25, "start_time": start.isoformat(), "end_time": (start + timedelta(hours=2)).isoformat()})
    by_name = {s["room"]["name"]: s for s in resp.json()}
    assert by_name["Mid"]["fit_quality"] == "good_fit"
    assert by_name["Big"]["fit_quality"] == "oversized"
    assert by_name["Closed small"]["closed"] is True
