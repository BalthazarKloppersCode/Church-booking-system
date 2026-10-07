from datetime import datetime

import pytest

from app import google_calendar, ical_feed
from app.config import settings

# Africa/Johannesburg is UTC+2 all year, so 08:00 local is 06:00 UTC.
FEED = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
X-WR-TIMEZONE:Africa/Johannesburg
BEGIN:VEVENT
UID:service@test
DTSTART;TZID=Africa/Johannesburg:20261011T090000
DTEND;TZID=Africa/Johannesburg:20261011T110000
RRULE:FREQ=WEEKLY;COUNT=3
SUMMARY:Sunday Service
END:VEVENT
BEGIN:VEVENT
UID:single@test
DTSTART:20261014T060000Z
DTEND:20261014T070000Z
SUMMARY:Elders meeting
END:VEVENT
BEGIN:VEVENT
UID:allday@test
DTSTART;VALUE=DATE:20261020
DTEND;VALUE=DATE:20261021
SUMMARY:Church camp
END:VEVENT
BEGIN:VEVENT
UID:private@test
DTSTART:20261015T060000Z
DTEND:20261015T070000Z
SUMMARY:Pastoral counselling
CLASS:PRIVATE
END:VEVENT
BEGIN:VEVENT
UID:cancelled@test
DTSTART:20261016T060000Z
DTEND:20261016T070000Z
SUMMARY:Called off
STATUS:CANCELLED
END:VEVENT
END:VCALENDAR
"""

WINDOW = (datetime(2026, 10, 1), datetime(2026, 11, 1))


class _Resp:
    def __init__(self, status=200, content=FEED):
        self.status_code = status
        self.content = content


class _Client:
    response = _Resp()
    fetches = 0

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, timeout=None):
        _Client.fetches += 1
        if isinstance(_Client.response, Exception):
            raise _Client.response
        return _Client.response


@pytest.fixture(autouse=True)
def feed(monkeypatch):
    _Client.response = _Resp()
    _Client.fetches = 0
    monkeypatch.setattr(ical_feed.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(settings, "google_calendar_ical_url", "https://calendar.google.com/calendar/ical/secret-token/basic.ics")
    monkeypatch.setattr(settings, "google_service_account_json", "")
    monkeypatch.setattr(settings, "church_timezone", "Africa/Johannesburg")
    ical_feed._cache.update(at=0.0, url=None, calendar=None)


async def test_events_are_read_in_utc_with_repeats_expanded():
    events = await ical_feed.list_events(*WINDOW)
    titles = [e["title"] for e in events]
    assert titles.count("Sunday Service") == 3
    services = [e for e in events if e["title"] == "Sunday Service"]
    assert services[0]["start_time"] == datetime(2026, 10, 11, 7, 0)  # 09:00 SAST
    assert services[0]["end_time"] == datetime(2026, 10, 11, 9, 0)
    assert [e["start_time"].day for e in services] == [11, 18, 25]
    elders = next(e for e in events if e["title"] == "Elders meeting")
    assert elders["start_time"] == datetime(2026, 10, 14, 6, 0)
    assert not elders["all_day"]


async def test_private_and_cancelled_events_are_never_shown():
    titles = [e["title"] for e in await ical_feed.list_events(*WINDOW)]
    assert "Pastoral counselling" not in titles
    assert "Called off" not in titles


async def test_all_day_events_start_at_local_midnight():
    camp = next(e for e in await ical_feed.list_events(*WINDOW) if e["title"] == "Church camp")
    assert camp["all_day"]
    assert camp["start_time"] == datetime(2026, 10, 19, 22, 0)  # 00:00 SAST on the 20th
    assert camp["end_time"] == datetime(2026, 10, 20, 22, 0)


async def test_only_events_inside_the_window_are_returned():
    events = await ical_feed.list_events(datetime(2026, 10, 13), datetime(2026, 10, 15))
    assert [e["title"] for e in events] == ["Elders meeting"]


async def test_the_feed_is_cached_between_requests():
    await ical_feed.list_events(*WINDOW)
    await ical_feed.list_events(*WINDOW)
    assert _Client.fetches == 1


async def test_a_failed_refresh_keeps_showing_the_last_good_copy(capsys):
    await ical_feed.list_events(*WINDOW)
    ical_feed._cache["at"] = 0.0  # expire it
    _Client.response = _Resp(500, b"")
    assert await ical_feed.list_events(*WINDOW)
    assert "Google answered 500" in capsys.readouterr().out


async def test_errors_never_leak_the_secret_url(capsys):
    _Client.response = OSError("could not connect to https://calendar.google.com/calendar/ical/secret-token/basic.ics")
    assert await ical_feed.list_events(*WINDOW) == []
    out = capsys.readouterr().out
    assert "[calendar feed error] OSError" in out
    assert "secret-token" not in out


async def test_garbage_in_the_feed_gives_an_empty_list_not_a_crash(capsys):
    _Client.response = _Resp(200, b"<html>not a calendar</html>")
    assert await ical_feed.list_events(*WINDOW) == []


async def test_nothing_is_fetched_when_no_feed_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_ical_url", "")
    assert await ical_feed.list_events(*WINDOW) == []
    assert _Client.fetches == 0


async def test_the_external_events_endpoint_serves_the_feed(client):
    resp = await client.get(
        "/api/bookings/calendar/external", params={"start_after": "2026-10-01T00:00:00", "start_before": "2026-11-01T00:00:00"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {e["title"] for e in body} == {"Sunday Service", "Elders meeting", "Church camp"}
    camp = next(e for e in body if e["title"] == "Church camp")
    assert camp["all_day"] is True
    assert camp["start_time"] == "2026-10-19T22:00:00+00:00"


async def test_the_service_account_takes_over_when_both_are_set(monkeypatch):
    monkeypatch.setattr(settings, "google_service_account_json", "{}")
    monkeypatch.setattr(settings, "google_calendar_id", "cal@group.calendar.google.com")

    async def fake_request(method, path, **kwargs):
        return {"items": [{"summary": "From the API", "start": {"date": "2026-10-20"}, "end": {"date": "2026-10-21"}}]}

    monkeypatch.setattr(google_calendar, "_request", fake_request)
    events = await google_calendar.list_external_events(*WINDOW)
    assert [e["title"] for e in events] == ["From the API"]
    assert events[0]["all_day"] is True
    assert events[0]["start_time"] == datetime(2026, 10, 19, 22, 0)
    assert _Client.fetches == 0
