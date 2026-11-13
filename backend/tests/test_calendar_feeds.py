from datetime import datetime

import pytest

from app import google_calendar, ical_feed
from app.config import settings
from tests.conftest import make_room
from tests.test_calendar_sync import _make_admin
from tests.test_ical_feed import FEED

WINDOW = (datetime(2026, 10, 1), datetime(2026, 11, 1))
MAIN = "https://calendar.google.com/calendar/ical/main-secret/basic.ics"
YOUTH = "https://calendar.google.com/calendar/ical/youth-secret/basic.ics"
KIDS = "https://calendar.google.com/calendar/ical/kids-secret/basic.ics"

# A second calendar that reuses the same event id as FEED's "Sunday Service": Friday 18:30 SAST weekly.
OTHER = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
X-WR-TIMEZONE:Africa/Johannesburg
BEGIN:VEVENT
UID:service@test
DTSTART;TZID=Africa/Johannesburg:20261016T183000
DTEND;TZID=Africa/Johannesburg:20261016T210000
RRULE:FREQ=WEEKLY;COUNT=2
SUMMARY:Youth Night
END:VEVENT
BEGIN:VEVENT
UID:private-thing@test
DTSTART:20261020T060000Z
DTEND:20261020T070000Z
SUMMARY:Counselling
CLASS:CONFIDENTIAL
END:VEVENT
END:VCALENDAR
"""


class _Resp:
    def __init__(self, status=200, content=OTHER):
        self.status_code = status
        self.content = content


class _Client:
    responses: dict = {}
    fetched: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, timeout=None):
        _Client.fetched.append(url)
        reply = _Client.responses.get(url, _Resp(404, b""))
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture(autouse=True)
def feeds(monkeypatch):
    _Client.responses = {YOUTH: _Resp(200, OTHER), KIDS: _Resp(200, FEED)}
    _Client.fetched = []
    monkeypatch.setattr(ical_feed.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(settings, "google_calendar_ical_url", "")
    monkeypatch.setattr(settings, "google_service_account_json", "")
    monkeypatch.setattr(settings, "church_timezone", "Africa/Johannesburg")


async def add(client, admin, name, url):
    return await client.post("/api/admin/calendar-feeds", json={"name": name, "url": url}, headers=admin)


# ---------- adding and managing calendars ----------


async def test_only_an_admin_can_manage_calendars(client):
    assert (await client.get("/api/admin/calendar-feeds")).status_code == 401
    assert (await client.post("/api/admin/calendar-feeds", json={"name": "x", "url": YOUTH})).status_code == 401


async def test_adding_a_calendar_checks_it_and_never_shows_the_secret_link(client):
    admin = await _make_admin(client)
    resp = await add(client, admin, "Youth", YOUTH)
    assert resp.status_code == 200, resp.text
    made = resp.json()
    assert made["name"] == "Youth" and made["enabled"] is True and made["ok"] is True
    assert "youth-secret" not in str(made)  # the link is a secret and isn't sent back
    assert made["link_hint"].endswith("asic.ics") and made["link_hint"].startswith("calendar.google.com")

    listed = (await client.get("/api/admin/calendar-feeds", headers=admin)).json()
    assert [f["name"] for f in listed] == ["Youth"] and "youth-secret" not in str(listed)


async def test_a_link_that_is_not_a_calendar_is_refused_with_a_reason(client, app_state):
    admin = await _make_admin(client)
    _Client.responses["https://example.com/page.html"] = _Resp(200, b"<html>hello</html>")
    _Client.responses["https://example.com/missing.ics"] = _Resp(404, b"")
    _Client.responses["https://example.com/down.ics"] = OSError("connection refused")
    for url, expected in (
        ("https://example.com/page.html", "isn't a calendar"),
        ("https://example.com/missing.ics", "answered 404"),
        ("https://example.com/down.ics", "reach that address"),
    ):
        resp = await add(client, admin, "Bad", url)
        assert resp.status_code == 400 and expected in resp.json()["detail"], url
    assert await app_state["feeds"].count_documents({}) == 0


async def test_unsafe_or_malformed_addresses_are_refused_before_anything_is_fetched(client):
    admin = await _make_admin(client)
    for bad in ("http://calendar.google.com/x.ics", "ftp://x.example.com/a.ics", "not a link", "https://localhost/a.ics",
                "https://127.0.0.1/a.ics", "https://10.0.0.5/a.ics", "https://192.168.1.10/a.ics", "https://169.254.169.254/latest",
                "https://printer.local/a.ics", "https://[::1]/a.ics"):
        resp = await add(client, admin, "Bad", bad)
        assert resp.status_code == 400, bad
    assert _Client.fetched == []


async def test_webcal_links_are_accepted(client):
    admin = await _make_admin(client)
    resp = await add(client, admin, "Youth", "webcal://calendar.google.com/calendar/ical/youth-secret/basic.ics")
    assert resp.status_code == 200
    assert _Client.fetched == [YOUTH]


async def test_the_same_calendar_cannot_be_added_twice(client):
    admin = await _make_admin(client)
    assert (await add(client, admin, "Youth", YOUTH)).status_code == 200
    again = await add(client, admin, "Youth again", YOUTH)
    assert again.status_code == 400 and "already been added" in again.json()["detail"]


async def test_a_calendar_can_be_turned_off_renamed_and_removed(client):
    admin = await _make_admin(client)
    feed = (await add(client, admin, "Youth", YOUTH)).json()

    off = await client.patch(f"/api/admin/calendar-feeds/{feed['id']}", json={"enabled": False, "name": "Youth team"}, headers=admin)
    assert off.json()["enabled"] is False and off.json()["name"] == "Youth team"
    assert await ical_feed.list_events(*WINDOW) == []  # off means not shown

    await client.patch(f"/api/admin/calendar-feeds/{feed['id']}", json={"enabled": True}, headers=admin)
    assert {e["calendar"] for e in await ical_feed.list_events(*WINDOW)} == {"Youth team"}

    assert (await client.delete(f"/api/admin/calendar-feeds/{feed['id']}", headers=admin)).status_code == 200
    assert await ical_feed.list_events(*WINDOW) == []
    assert (await client.delete(f"/api/admin/calendar-feeds/{feed['id']}", headers=admin)).status_code == 404
    assert (await client.patch("/api/admin/calendar-feeds/not-an-id", json={"enabled": True}, headers=admin)).status_code == 404


async def test_the_page_reports_when_a_saved_calendar_stops_working(client):
    admin = await _make_admin(client)
    await add(client, admin, "Youth", YOUTH)
    ical_feed._cache.clear()
    _Client.responses[YOUTH] = _Resp(410, b"")
    row = (await client.get("/api/admin/calendar-feeds", headers=admin)).json()[0]
    assert row["ok"] is False and "answered 410" in row["error"]


async def test_the_calendar_from_the_server_settings_is_listed_and_cannot_be_duplicated(client, monkeypatch):
    admin = await _make_admin(client)
    monkeypatch.setattr(settings, "google_calendar_ical_url", MAIN)
    _Client.responses[MAIN] = _Resp(200, FEED)
    listed = (await client.get("/api/admin/calendar-feeds", headers=admin)).json()
    assert listed[0]["built_in"] is True and listed[0]["id"] is None and "main-secret" not in str(listed)
    assert (await add(client, admin, "Same again", MAIN)).status_code == 400


# ---------- merged events ----------


async def test_events_from_every_calendar_are_merged_and_labelled(client, monkeypatch):
    admin = await _make_admin(client)
    monkeypatch.setattr(settings, "google_calendar_ical_url", MAIN)
    _Client.responses[MAIN] = _Resp(200, FEED)
    await add(client, admin, "Youth", YOUTH)

    events = await ical_feed.list_events(*WINDOW)
    by_calendar = {}
    for e in events:
        by_calendar.setdefault(e["calendar"], set()).add(e["title"])
    assert by_calendar == {
        "church calendar": {"Sunday Service", "Elders meeting", "Church camp"},
        "Youth": {"Youth Night"},
    }
    assert [e["start_time"] for e in events] == sorted(e["start_time"] for e in events)
    assert "Counselling" not in {e["title"] for e in events}  # private events stay hidden in every calendar


async def test_one_broken_calendar_does_not_hide_the_others(client, monkeypatch):
    admin = await _make_admin(client)
    await add(client, admin, "Youth", YOUTH)
    await add(client, admin, "Kids", KIDS)
    ical_feed._cache.clear()
    _Client.responses[YOUTH] = OSError("down")
    events = await ical_feed.list_events(*WINDOW)
    assert {e["calendar"] for e in events} == {"Kids"}


async def test_the_events_endpoint_serves_every_calendar_with_its_name(client):
    admin = await _make_admin(client)
    await add(client, admin, "Youth", YOUTH)
    body = (await client.get("/api/bookings/calendar/external", params={"start_after": "2026-10-01T00:00:00", "start_before": "2026-11-01T00:00:00"})).json()
    assert {e["calendar"] for e in body} == {"Youth"} and all(e["uid"].startswith("feed:") for e in body)


async def test_two_calendars_that_reuse_an_event_id_never_collide(client, rooms_col, monkeypatch):
    admin = await _make_admin(client)
    monkeypatch.setattr(settings, "google_calendar_ical_url", MAIN)
    _Client.responses[MAIN] = _Resp(200, FEED)  # its "service@test" is Sunday Service
    feed = (await add(client, admin, "Youth", YOUTH)).json()  # its "service@test" is Youth Night

    youth_uid = f"feed:{feed['id']}:service@test"
    only_youth = await ical_feed.list_events(*WINDOW, uids={youth_uid})
    assert {e["title"] for e in only_youth} == {"Youth Night"}
    only_main = await ical_feed.list_events(*WINDOW, uids={"service@test"})
    assert {e["title"] for e in only_main} == {"Sunday Service"}

    # Giving the youth event a room blocks the room on Friday evenings, and leaves Sunday mornings alone.
    hall = await make_room(rooms_col, name="Hall", capacity=300)
    assert (await client.put("/api/admin/calendar-events/rooms", json={"uid": youth_uid, "title": "Youth Night", "room_ids": [hall]}, headers=admin)).status_code == 200
    from app import church_events

    friday_evening = (datetime(2026, 10, 16, 17, 0), datetime(2026, 10, 16, 18, 0))  # 19:00-20:00 SAST
    sunday_morning = (datetime(2026, 10, 18, 7, 30), datetime(2026, 10, 18, 8, 30))
    assert (await church_events.blocking_event(hall, *friday_evening))["title"] == "Youth Night"
    assert await church_events.blocking_event(hall, *sunday_morning) is None


async def test_the_service_account_calendar_and_the_added_ones_are_shown_together(client, monkeypatch):
    admin = await _make_admin(client)
    await add(client, admin, "Youth", YOUTH)
    monkeypatch.setattr(settings, "google_service_account_json", "{}")
    monkeypatch.setattr(settings, "google_calendar_id", "cal@group.calendar.google.com")

    async def fake_request(method, path, **kwargs):
        return {"items": [{"id": "api1", "summary": "From the API", "start": {"dateTime": "2026-10-14T08:00:00Z"}, "end": {"dateTime": "2026-10-14T09:00:00Z"}}]}

    monkeypatch.setattr(google_calendar, "_request", fake_request)
    events = await google_calendar.list_external_events(*WINDOW)
    assert {(e["title"], e["calendar"]) for e in events} == {("From the API", "church calendar"), ("Youth Night", "Youth")}
    assert [e["start_time"] for e in events] == sorted(e["start_time"] for e in events)
