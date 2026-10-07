"""
Read-only pull of the church's Google Calendar through its "secret address in
iCal format" — no Google Cloud project, service account or OAuth needed.

In Google Calendar: Settings -> pick the calendar -> Integrate calendar ->
"Secret address in iCal format". Put that URL in GOOGLE_CALENDAR_ICAL_URL.
Anyone holding the URL can read the whole calendar, so treat it like a
password: it lives only in the environment, and it is never logged (httpx's own
error text includes the URL, so errors are reported by type/status only).

Events marked Private/Confidential in Google are skipped — the endpoint that
serves these titles is public, so only events the church treats as ordinary
calendar entries are shown. Recurring events are expanded for the requested
window. The fetched feed is cached for a few minutes so a busy page doesn't
hammer Google, and a failed refresh falls back to the last good copy.

Like email/WhatsApp, a broken feed returns an empty list and logs a line; it
must never break the calendar pages.
"""
import asyncio
import time as _time
from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

from app.config import settings

CACHE_SECONDS = 300
MAX_EVENTS = 500
HIDDEN_CLASSES = {"PRIVATE", "CONFIDENTIAL"}

_cache: dict = {"at": 0.0, "url": None, "calendar": None}


def enabled() -> bool:
    return bool(settings.google_calendar_ical_url.strip())


def to_utc_naive(value, tz: ZoneInfo) -> tuple[datetime, bool]:
    """(naive UTC datetime, is_all_day). Floating times and all-day dates are read in `tz`."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return value.astimezone(timezone.utc).replace(tzinfo=None), False
    if isinstance(value, date):
        midnight = datetime.combine(value, time.min, tzinfo=tz)
        return midnight.astimezone(timezone.utc).replace(tzinfo=None), True
    raise ValueError(f"Unsupported calendar value: {type(value).__name__}")


async def _load_calendar() -> Optional[icalendar.Calendar]:
    url = settings.google_calendar_ical_url.strip()
    now = _time.monotonic()
    if _cache["calendar"] is not None and _cache["url"] == url and now - _cache["at"] < CACHE_SECONDS:
        return _cache["calendar"]
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=15)
        if resp.status_code >= 400:
            print(f"[calendar feed error] Google answered {resp.status_code} — check GOOGLE_CALENDAR_ICAL_URL", flush=True)
            return _cache["calendar"] if _cache["url"] == url else None
        calendar = await asyncio.to_thread(icalendar.Calendar.from_ical, resp.content)
    except Exception as e:
        print(f"[calendar feed error] {type(e).__name__}", flush=True)
        return _cache["calendar"] if _cache["url"] == url else None
    _cache.update(at=now, url=url, calendar=calendar)
    return calendar


def _extract(calendar: icalendar.Calendar, start: datetime, end: datetime) -> list[dict]:
    tz = ZoneInfo(settings.church_timezone)
    found = recurring_ical_events.of(calendar).between(
        start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)
    )
    events = []
    for component in found:
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue
        if str(component.get("CLASS", "")).upper() in HIDDEN_CLASSES:
            continue
        try:
            start_time, all_day = to_utc_naive(component.start, tz)
            end_time, _ = to_utc_naive(component.end, tz)
        except Exception:
            continue
        events.append(
            {
                "title": str(component.get("SUMMARY", "")).strip() or "(Untitled event)",
                "start_time": start_time,
                "end_time": end_time,
                "all_day": all_day,
            }
        )
    events.sort(key=lambda e: e["start_time"])
    return events[:MAX_EVENTS]


async def list_events(start_after: datetime, start_before: datetime) -> list[dict]:
    """Events on the church calendar between two naive-UTC datetimes."""
    if not enabled():
        return []
    calendar = await _load_calendar()
    if calendar is None:
        return []
    try:
        return await asyncio.to_thread(_extract, calendar, start_after, start_before)
    except Exception as e:
        print(f"[calendar feed error] could not read events: {type(e).__name__}", flush=True)
        return []
