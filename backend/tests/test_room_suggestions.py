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


# ---- per-room minimum people (Manage Rooms) ----

async def _admin_headers(client):
    from app.config import settings

    await client.post(
        "/api/admin/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "hunter22", "setup_secret": settings.admin_setup_secret},
    )
    login = await client.post("/api/admin/login", json={"email": "alice@example.com", "password": "hunter22"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _by_name(response):
    return {s["room"]["name"]: s for s in response.json()}


async def test_group_under_a_rooms_minimum_is_blocked_with_a_reason(client, rooms_col):
    await make_room(rooms_col, name="Classroom", type="classroom", capacity=30)
    await make_room(rooms_col, name="Training Hall", type="training_hall", capacity=200, min_people=40)

    suggestions = _by_name(await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=20)))
    assert suggestions["Training Hall"]["fit_quality"] == "oversized"
    assert suggestions["Training Hall"]["note"] == "Needs at least 40 people"
    assert suggestions["Classroom"]["fit_quality"] == "good_fit"


async def test_room_with_a_minimum_is_offered_across_its_whole_range(client, rooms_col):
    # 55 people used to leave only the Coffee Shop: the 200-seat Training Hall
    # was auto-blocked as "too large". With a configured minimum it's offered.
    await make_room(rooms_col, name="Coffee Shop", type="coffee_shop", capacity=70)
    await make_room(rooms_col, name="Training Hall", type="training_hall", capacity=200, min_people=40)
    await make_room(rooms_col, name="Main Hall", type="main_hall", capacity=600)

    suggestions = _by_name(await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=55)))
    assert suggestions["Coffee Shop"]["fit_quality"] == "good_fit"
    assert suggestions["Training Hall"]["fit_quality"] == "good_fit"
    assert suggestions["Training Hall"]["note"] is None
    # No minimum configured: the automatic size rule still applies.
    assert suggestions["Main Hall"]["fit_quality"] == "oversized"


async def test_room_under_its_minimum_is_not_the_reference_for_the_size_rule(client, rooms_col):
    # Coffee Shop is out for 20 people, so it must not be the "right-sized"
    # reference that then blocks the only other room that fits.
    await make_room(rooms_col, name="Coffee Shop", type="coffee_shop", capacity=70, min_people=30)
    await make_room(rooms_col, name="Main Hall", type="main_hall", capacity=600)

    suggestions = _by_name(await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=20)))
    assert suggestions["Coffee Shop"]["fit_quality"] == "oversized"
    assert suggestions["Main Hall"]["fit_quality"] == "good_fit"


async def test_automatic_rule_still_explains_itself(client, rooms_col):
    await make_room(rooms_col, name="Classroom", type="classroom", capacity=30)
    await make_room(rooms_col, name="Main Hall", type="main_hall", capacity=600)
    suggestions = _by_name(await client.post("/api/rooms/suggest", json=_suggestion_request(headcount=20)))
    assert suggestions["Main Hall"]["note"] == "Too large for your group — pick a smaller room"


async def test_create_room_rejects_a_minimum_above_capacity(client):
    headers = await _admin_headers(client)
    body = {"name": "Hall", "type": "main_hall", "capacity": 20, "min_people": 30}
    assert (await client.post("/api/rooms", json=body, headers=headers)).status_code == 422
    ok = await client.post("/api/rooms", json={**body, "min_people": 10}, headers=headers)
    assert ok.status_code == 200 and ok.json()["min_people"] == 10


async def test_minimum_can_be_set_changed_and_cleared_on_update(client, rooms_col):
    headers = await _admin_headers(client)
    room_id = await make_room(rooms_col, name="Hall", type="training_hall", capacity=100)

    set_ = await client.patch(f"/api/rooms/{room_id}", json={"min_people": 40}, headers=headers)
    assert set_.json()["min_people"] == 40

    untouched = await client.patch(f"/api/rooms/{room_id}", json={"name": "Hall B"}, headers=headers)
    assert untouched.json()["min_people"] == 40  # omitted means unchanged

    cleared = await client.patch(f"/api/rooms/{room_id}", json={"min_people": None}, headers=headers)
    assert cleared.json()["min_people"] is None

    too_high = await client.patch(f"/api/rooms/{room_id}", json={"min_people": 500}, headers=headers)
    assert too_high.status_code == 400

    lowering_capacity = await client.patch(f"/api/rooms/{room_id}", json={"min_people": 60}, headers=headers)
    assert lowering_capacity.status_code == 200
    below = await client.patch(f"/api/rooms/{room_id}", json={"capacity": 50}, headers=headers)
    assert below.status_code == 400  # would leave min (60) above the new capacity
