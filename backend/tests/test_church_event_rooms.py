from datetime import datetime, timedelta

import pytest

from app import google_calendar, ical_feed
from app.config import settings
from tests.conftest import booking_payload, make_room
from tests.test_calendar_sync import _make_admin
from tests.test_ical_feed import FEED, _Client, _Resp

# From the feed in test_ical_feed: "Sunday Service" (uid service@test) repeats
# weekly on 11, 18 and 25 Oct 2026, 07:00–09:00 UTC. "Elders meeting" is a
# single event on 14 Oct, 06:00–07:00 UTC.
SERVICE = "service@test"


@pytest.fixture(autouse=True)
def feed(monkeypatch):
    _Client.response = _Resp(200, FEED)
    _Client.fetches = 0
    monkeypatch.setattr(ical_feed.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(settings, "google_calendar_ical_url", "https://calendar.example/secret/basic.ics")
    monkeypatch.setattr(settings, "google_service_account_json", "")
    monkeypatch.setattr(settings, "church_timezone", "Africa/Johannesburg")
    ical_feed._cache.update(at=0.0, url=None, calendar=None)


def _at(day, start_hour, end_hour):
    return {
        "start_time": datetime(2026, 10, day, start_hour).isoformat(),
        "end_time": datetime(2026, 10, day, end_hour).isoformat(),
    }


async def _assign(client, headers, room_ids, uid=SERVICE):
    return await client.put(
        "/api/admin/calendar-events/rooms", json={"uid": uid, "title": "Sunday Service", "room_ids": room_ids}, headers=headers
    )


async def test_only_an_admin_can_assign_rooms(client, rooms_col):
    room_id = await make_room(rooms_col)
    resp = await _assign(client, {}, [room_id])
    assert resp.status_code in (401, 403)


async def test_assigning_a_room_is_saved_and_shows_on_the_event(client, rooms_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall")
    resp = await _assign(client, admin, [hall, hall])  # duplicates collapse
    assert resp.status_code == 200
    assert resp.json()["room_ids"] == [hall]

    events = (
        await client.get("/api/bookings/calendar/external", params={"start_after": "2026-10-01T00:00:00", "start_before": "2026-11-01T00:00:00"})
    ).json()
    services = [e for e in events if e["title"] == "Sunday Service"]
    assert len(services) == 3 and all(e["room_ids"] == [hall] and e["uid"] == SERVICE for e in services)
    assert next(e for e in events if e["title"] == "Elders meeting")["room_ids"] == []


async def test_an_unknown_room_is_rejected_and_nothing_is_saved(client, rooms_col, app_state):
    admin = await _make_admin(client)
    resp = await _assign(client, admin, ["64b000000000000000000000"])
    assert resp.status_code == 404
    assert await app_state["event_rooms"].count_documents({}) == 0
    assert (await _assign(client, admin, ["not-an-id"])).status_code == 404


async def test_one_assignment_blocks_every_date_of_a_repeating_event(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await _assign(client, admin, [hall])

    for day in (11, 18, 25):  # every Sunday of the series
        resp = await client.post(
            "/api/bookings", json=booking_payload(hall, **{}) | _at(day, 7, 8), headers=booker_headers
        )
        assert resp.status_code == 409, day
        assert "Sunday Service" in resp.json()["detail"] and "Main Hall" in resp.json()["detail"]


async def test_rooms_and_times_outside_the_event_stay_bookable(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    other = await make_room(rooms_col, name="Training Hall", capacity=60)
    await _assign(client, admin, [hall])

    # Different room, same time.
    assert (await client.post("/api/bookings", json=booking_payload(other) | _at(18, 7, 8), headers=booker_headers)).status_code == 200
    # Same room, straight after the event ends (09:00 UTC) and a different Sunday-less day.
    assert (await client.post("/api/bookings", json=booking_payload(hall) | _at(18, 9, 10), headers=booker_headers)).status_code == 200
    assert (await client.post("/api/bookings", json=booking_payload(hall) | _at(19, 7, 8), headers=booker_headers)).status_code == 200


async def test_an_event_can_hold_several_rooms(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    foyer = await make_room(rooms_col, name="Foyer", capacity=80)
    await _assign(client, admin, [hall, foyer])
    for room in (hall, foyer):
        resp = await client.post("/api/bookings", json=booking_payload(room) | _at(11, 8, 9), headers=booker_headers)
        assert resp.status_code == 409


async def test_clearing_the_rooms_frees_them_again(client, rooms_col, booker_headers):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await _assign(client, admin, [hall])
    assert (await client.post("/api/bookings", json=booking_payload(hall) | _at(11, 7, 8), headers=booker_headers)).status_code == 409

    cleared = await _assign(client, admin, [])
    assert cleared.status_code == 200 and cleared.json()["room_ids"] == []
    assert (await client.post("/api/bookings", json=booking_payload(hall) | _at(11, 7, 8), headers=booker_headers)).status_code == 200


async def test_room_suggestions_mark_an_event_room_as_busy(client, rooms_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await _assign(client, admin, [hall])
    body = {"headcount": 100, **_at(11, 7, 8)}
    suggestions = (await client.post("/api/rooms/suggest", json=body)).json()
    assert [s["available"] for s in suggestions if s["room"]["id"] == hall] == [False]

    later = {"headcount": 100, **_at(11, 10, 11)}
    suggestions = (await client.post("/api/rooms/suggest", json=later)).json()
    assert [s["available"] for s in suggestions if s["room"]["id"] == hall] == [True]


async def test_an_admin_series_that_runs_into_the_event_is_refused_whole(client, rooms_col, bookings_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await _assign(client, admin, [hall])
    payload = {
        "room_id": hall,
        "requester_name": "Office",
        "congregation": "Youth Group",
        "email": "office@example.com",
        "phone": "+10000000000",
        "headcount": 20,
        "purpose": "Bible study",
        "is_private_event": False,
        "recurrence": {"frequency": "weekly", "until": "2026-10-30T00:00:00Z"},
        **_at(4, 7, 8),  # Sunday 4 Oct (no event) then 11 Oct (event) ...
    }
    resp = await client.post("/api/admin/bookings", json=payload, headers=admin)
    assert resp.status_code == 409
    assert await bookings_col.count_documents({}) == 0


async def test_existing_bookings_that_clash_are_reported_not_cancelled(client, rooms_col, bookings_col, booker_headers, monkeypatch):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    created = await client.post("/api/bookings", json=booking_payload(hall) | _at(18, 7, 8), headers=booker_headers)
    assert created.status_code == 200

    # The clash check looks 90 days ahead of the real clock, so give it an
    # event that's actually upcoming rather than relying on the fixed feed dates.
    soon = datetime(2026, 10, 18, 7, 0)

    async def fake_list(start, end, uids=None):
        return [{"uid": SERVICE, "title": "Sunday Service", "start_time": soon, "end_time": soon + timedelta(hours=2), "all_day": False}]

    monkeypatch.setattr(google_calendar, "list_external_events", fake_list)
    from app import church_events

    class _Now(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 10, 13)

    monkeypatch.setattr(church_events, "datetime", _Now)

    admin = await _make_admin(client)
    resp = await _assign(client, admin, [hall])
    clashes = resp.json()["clashes"]
    assert len(clashes) == 1
    assert clashes[0]["room_name"] == "Room A" or clashes[0]["congregation"] == "Youth Group"
    assert clashes[0]["event_title"] == "Sunday Service"
    assert (await bookings_col.find_one({"status": "pending"})) or (await bookings_col.find_one({"status": "approved"}))


async def test_only_the_assigned_events_are_expanded_when_checking_a_room():
    events = await ical_feed.list_events(datetime(2026, 10, 1), datetime(2026, 11, 1), uids={SERVICE})
    assert {e["title"] for e in events} == {"Sunday Service"} and len(events) == 3
    assert await ical_feed.list_events(datetime(2026, 10, 1), datetime(2026, 11, 1), uids=set()) == []


async def test_nothing_is_read_from_the_feed_when_no_room_is_assigned(client, rooms_col, booker_headers):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    _Client.fetches = 0
    resp = await client.post("/api/bookings", json=booking_payload(hall) | _at(11, 7, 8), headers=booker_headers)
    assert resp.status_code == 200
    assert _Client.fetches == 0
