from datetime import datetime, timedelta

from tests.conftest import make_room


def _suggestion_request(headcount, room_type=None):
    start = datetime.utcnow() + timedelta(days=3)
    end = start + timedelta(hours=2)
    payload = {
        "headcount": headcount,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }
    if room_type:
        payload["type"] = room_type
    return payload


async def test_suggests_smallest_sufficient_room_first(client, rooms_col):
    await make_room(rooms_col, name="Small", capacity=15)
    await make_room(rooms_col, name="Medium", capacity=30)
    await make_room(rooms_col, name="Large", capacity=100)

    resp = await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=20))
    assert resp.status_code == 200
    suggestions = resp.json()

    fitting = [s for s in suggestions if s["room"]["capacity"] >= 20]
    assert fitting[0]["room"]["name"] == "Medium"
    assert fitting[0]["fit_quality"] == "good_fit"


async def test_too_small_rooms_are_flagged(client, rooms_col):
    await make_room(rooms_col, name="Tiny", capacity=5)

    resp = await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=20))
    assert resp.status_code == 200
    suggestions = resp.json()
    assert any(s["fit_quality"] == "too_small" for s in suggestions)


async def test_falls_back_to_largest_rooms_when_nothing_fits(client, rooms_col):
    await make_room(rooms_col, name="Only Room", capacity=5)

    resp = await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=500))
    assert resp.status_code == 200
    suggestions = resp.json()
    assert len(suggestions) >= 1
    assert suggestions[0]["fit_quality"] == "too_small"


async def test_oversized_non_classroom_room_is_blocked(client, rooms_col):
    await make_room(rooms_col, name="Small Classroom", type="classroom", capacity=30)
    await make_room(rooms_col, name="Huge Hall", type="main_hall", capacity=600)

    resp = await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=20))
    assert resp.status_code == 200
    suggestions = {s["room"]["name"]: s for s in resp.json()}

    assert suggestions["Huge Hall"]["fit_quality"] == "oversized"
    assert suggestions["Small Classroom"]["fit_quality"] == "good_fit"


async def test_classroom_type_rooms_are_exempt_from_oversized_block(client, rooms_col):
    await make_room(rooms_col, name="Big Leap Room", type="leap", capacity=30)
    await make_room(rooms_col, name="Huge Hall", type="main_hall", capacity=600)

    # Headcount of 2 makes both rooms wildly oversized relative to what's
    # needed, but the leap room is exempt since it's already the smallest
    # category — only the non-classroom room should be blocked.
    resp = await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=2))
    suggestions = {s["room"]["name"]: s for s in resp.json()}
    assert suggestions["Big Leap Room"]["fit_quality"] == "good_fit"
    assert suggestions["Huge Hall"]["fit_quality"] == "oversized"


async def test_smallest_fitting_non_classroom_room_is_not_blocked(client, rooms_col):
    """
    A group too big for any classroom shouldn't have every non-classroom
    option blocked as "oversized" — the smallest one that actually fits
    must stay available, or nothing would be bookable at all.
    """
    await make_room(rooms_col, name="Classroom", type="classroom", capacity=30)
    await make_room(rooms_col, name="Coffee Shop", type="coffee_shop", capacity=70)
    await make_room(rooms_col, name="Main Hall", type="main_hall", capacity=600)

    resp = await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=35))
    suggestions = {s["room"]["name"]: s for s in resp.json()}
    # The classroom doesn't meet the headcount at all, so it's outside the
    # main candidate query entirely (covered by test_too_small_rooms_are_flagged
    # via the "nothing fits" fallback path) — what matters here is that the
    # smallest room that *does* fit stays selectable.
    assert suggestions["Coffee Shop"]["fit_quality"] == "good_fit"
    assert suggestions["Main Hall"]["fit_quality"] == "oversized"


async def test_suggestion_reflects_room_already_booked(client, rooms_col, booker_headers):
    room_id = await make_room(rooms_col, name="Busy Room", capacity=30)
    req = _suggestion_request(headcount=20)

    booking_payload = {
        "room_id": room_id,
        "requester_name": "Jane Doe",
        "congregation": "Youth Group",
        "email": "jane@example.com",
        "phone": "+10000000000",
        "headcount": 10,
        "start_time": req["start_time"],
        "end_time": req["end_time"],
        "purpose": "Bible study",
        "is_private_event": False,
    }
    booked = await client.post("/api/bookings", json=booking_payload, headers=booker_headers)
    assert booked.status_code == 200

    resp = await client.post("/api/rooms/suggest", json=req)
    suggestion = next(s for s in resp.json() if s["room"]["name"] == "Busy Room")
    assert suggestion["available"] is False
