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


async def test_suggestion_reflects_room_already_booked(client, rooms_col):
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
    booked = await client.post("/api/bookings", json=booking_payload)
    assert booked.status_code == 200

    resp = await client.post("/api/rooms/suggest", json=req)
    suggestion = next(s for s in resp.json() if s["room"]["name"] == "Busy Room")
    assert suggestion["available"] is False
