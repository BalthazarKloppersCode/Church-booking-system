"""
Read-only pull of the church's Google Calendars through their "secret address in
iCal format": no Google Cloud project, service account or OAuth needed.

Each Google calendar has its own secret address (Calendar settings -> the
calendar -> Integrate calendar). The office adds as many as it likes on the
admin "Calendars" page; there may also be one set in the server settings
(GOOGLE_CALENDAR_ICAL_URL), which keeps working and is shown as the main church
calendar. Everything is merged into one list, each event labelled with the name
of the calendar it came from.

Anyone holding a secret address can read that whole calendar, so treat it like a
password: it is never logged (httpx's own error text includes the URL, so errors
are reported by kind only) and never sent back to the browser.

Events marked Private/Confidential in Google are skipped: the endpoint that serves
these titles is public, so only events the church treats as ordinary calendar
entries are shown. Recurring events are expanded for the requested window. Each
fetched feed is cached for a few minutes so a busy page doesn't hammer Google, and
a failed refresh falls back to the last good copy. One broken feed never hides the
others, and a broken feed never breaks the calendar pages.

Event ids: a repeating event is one UID, which is how a room assignment covers every
date. UIDs from the added calendars are prefixed `feed:<id>:` so two calendars can
never collide; the one from the server settings keeps its plain UID, so assignments
made before there were several calendars still hold.
"""
import asyncio
import ipaddress
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

from app.config import settings
from app.database import calendar_feeds_collection

CACHE_SECONDS = 300
MAX_EVENTS = 500
HIDDEN_CLASSES = {"PRIVATE", "CONFIDENTIAL"}
LEGACY_NAME = "church calendar"
FEED_PREFIX = "feed:"

_cache: dict[str, tuple[float, icalendar.Calendar]] = {}
_errors: dict[str, str] = {}


class FeedError(ValueError):
    """A calendar link that can't be used, in words the office can act on."""


def feed_prefix(feed_id: str) -> str:
    return f"{FEED_PREFIX}{feed_id}:"


def legacy_enabled() -> bool:
    return bool(settings.google_calendar_ical_url.strip())


def enabled() -> bool:
    """Whether the calendar from the server settings is set (used for the startup log)."""
    return legacy_enabled()


def normalize_url(raw: str) -> str:
    """https only, no local or private addresses: the server fetches this link, so it must be a public one."""
    url = (raw or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise FeedError("Paste the whole link, starting with https://")
    if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        raise FeedError("That address isn't a public calendar link")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url  # a normal host name
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        raise FeedError("That address isn't a public calendar link")
    return url


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


async def fetch_calendar(url: str) -> tuple[Optional[icalendar.Calendar], Optional[str]]:
    """Downloads and parses one feed: (calendar, None) or (None, what went wrong in plain words)."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=15)
    except Exception as e:
        print(f"[calendar feed error] could not reach a calendar ({type(e).__name__})", flush=True)
        return None, "Couldn't reach that address"
    if resp.status_code >= 400:
        print(f"[calendar feed error] a calendar's server answered {resp.status_code}", flush=True)
        return None, f"The calendar's server answered {resp.status_code}, so the link may be wrong or switched off"
    try:
        return await asyncio.to_thread(icalendar.Calendar.from_ical, resp.content), None
    except Exception as e:
        print(f"[calendar feed error] a link isn't a calendar ({type(e).__name__})", flush=True)
        return None, "That link isn't a calendar feed"


async def _load(url: str) -> Optional[icalendar.Calendar]:
    now = _time.monotonic()
    hit = _cache.get(url)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    calendar, error = await fetch_calendar(url)
    if calendar is None:
        _errors[url] = error or "Couldn't read this calendar"
        return hit[1] if hit else None  # keep showing the last good copy
    _errors.pop(url, None)
    _cache[url] = (now, calendar)
    return calendar


def remember(url: str, calendar: icalendar.Calendar) -> None:
    """Keeps a calendar just downloaded (for example while checking a new link) so it isn't fetched twice."""
    _errors.pop(url, None)
    _cache[url] = (_time.monotonic(), calendar)


def forget(url: str) -> None:
    _cache.pop(url, None)
    _errors.pop(url, None)


def _only(calendar: icalendar.Calendar, uids: set[str]) -> icalendar.Calendar:
    """A copy holding just the wanted events (plus timezone definitions) — so
    expanding repeats only does the work for events we actually care about."""
    sub = icalendar.Calendar()
    for key, value in calendar.items():
        sub[key] = value
    for component in calendar.subcomponents:
        if component.name == "VTIMEZONE" or (component.name == "VEVENT" and str(component.get("UID", "")) in uids):
            sub.add_component(component)
    return sub


def _extract(calendar: icalendar.Calendar, start: datetime, end: datetime, uids: Optional[set[str]] = None) -> list[dict]:
    tz = ZoneInfo(settings.church_timezone)
    if uids is not None:
        calendar = _only(calendar, uids)
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
                "uid": str(component.get("UID", "")),
                "title": str(component.get("SUMMARY", "")).strip() or "(Untitled event)",
                "start_time": start_time,
                "end_time": end_time,
                "all_day": all_day,
            }
        )
    events.sort(key=lambda e: e["start_time"])
    return events[:MAX_EVENTS]


async def _active_feeds(include_legacy: bool) -> list[dict]:
    feeds = []
    if include_legacy and legacy_enabled():
        feeds.append({"prefix": "", "name": LEGACY_NAME, "url": settings.google_calendar_ical_url.strip()})
    try:
        async for doc in calendar_feeds_collection.find({"enabled": {"$ne": False}}).sort("created_at", 1):
            feeds.append({"prefix": feed_prefix(str(doc["_id"])), "name": doc["name"], "url": doc["url"]})
    except Exception as e:
        print(f"[calendar feed error] couldn't read the list of calendars ({type(e).__name__})", flush=True)
    return feeds


async def _events_for(feed: dict, start: datetime, end: datetime, uids: Optional[set[str]]) -> list[dict]:
    prefix = feed["prefix"]
    wanted = None
    if uids is not None:
        wanted = {u[len(prefix):] for u in uids if u.startswith(prefix)} if prefix else {u for u in uids if not u.startswith(FEED_PREFIX)}
        if not wanted:
            return []
    calendar = await _load(feed["url"])
    if calendar is None:
        return []
    try:
        events = await asyncio.to_thread(_extract, calendar, start, end, wanted)
    except Exception as e:
        print(f"[calendar feed error] could not read events: {type(e).__name__}", flush=True)
        return []
    for event in events:
        event["uid"] = prefix + event["uid"]
        event["calendar"] = feed["name"]
    return events


async def list_events(
    start_after: datetime, start_before: datetime, uids: Optional[set[str]] = None, include_legacy: bool = True
) -> list[dict]:
    """
    Events from every calendar between two naive-UTC datetimes, newest information first
    from cache, each labelled with its calendar. Only events with the given UIDs, if any
    are given. `include_legacy=False` leaves out the calendar from the server settings
    (used when the two-way Google sync already covers it).
    """
    feeds = await _active_feeds(include_legacy)
    if not feeds:
        return []
    batches = await asyncio.gather(*(_events_for(f, start_after, start_before, uids) for f in feeds))
    merged = [event for batch in batches for event in batch]
    merged.sort(key=lambda e: e["start_time"])
    return merged[:MAX_EVENTS]


async def feed_status(url: str) -> dict:
    """What the admin page shows beside a calendar: whether it can be read, and how much is coming up."""
    calendar = await _load(url)
    if calendar is None:
        return {"ok": False, "error": _errors.get(url, "Couldn't read this calendar"), "upcoming": 0}
    now = datetime.utcnow()
    try:
        upcoming = len(await asyncio.to_thread(_extract, calendar, now, now + timedelta(days=90), None))
    except Exception:
        return {"ok": False, "error": "This calendar couldn't be read", "upcoming": 0}
    return {"ok": True, "error": None, "upcoming": upcoming}
