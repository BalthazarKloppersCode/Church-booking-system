"""
Raw Google Calendar REST wrapper for the two-way sync with the church's
shared calendar (e.g. "LINKTREE Durbanville AM Events"):

- Push: approved bookings are created as events on the calendar so
  staff/leadership see them in their normal calendar app. Cancelling a
  booking removes the event; editing an approved booking's time/room
  updates it. Every event this app creates is tagged with a private
  extended property so it can be told apart from events already on the
  calendar.
- Pull: `list_external_events` returns events on the calendar that this app
  did NOT create (existing services, external bookings, etc.) — used to
  overlay them on the booker/admin calendar views, filtering out our own
  tagged events so nothing shows up twice.

Auth is a Google service account — no interactive OAuth/consent flow, no
refresh tokens to babysit. Share the target calendar with the service
account's email ("Make changes to events" for two-way) and set
GOOGLE_SERVICE_ACCOUNT_JSON + GOOGLE_CALENDAR_ID in the environment.

If either is unset, every function here is a silent no-op (logged), same
resilience pattern as email/WhatsApp in notifications.py — a misconfigured
or unreachable Google API must never break the booking flow itself.
"""
import asyncio
import json
from datetime import date, datetime, time, timezone
from typing import Optional

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]
API_BASE = "https://www.googleapis.com/calendar/v3"
EXT_PROP_KEY = "booking_app"  # extendedProperties.private marker for events we created

_credentials: Optional[service_account.Credentials] = None


def _enabled() -> bool:
    return bool(settings.google_service_account_json and settings.google_calendar_id)


async def _get_access_token() -> Optional[str]:
    global _credentials
    if not settings.google_service_account_json:
        return None
    if _credentials is None:
        info = json.loads(settings.google_service_account_json)
        _credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if not _credentials.valid:
        # google-auth's refresh() is a blocking HTTP call — push it to a
        # thread so it doesn't stall the event loop for every other request.
        await asyncio.to_thread(_credentials.refresh, GoogleAuthRequest())
    return _credentials.token


async def _request(method: str, path: str, **kwargs) -> Optional[dict]:
    token = await _get_access_token()
    if token is None:
        return None
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    url = f"{API_BASE}{path}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, headers=headers, timeout=10, **kwargs)
        if resp.status_code >= 400:
            # 404/410 on a delete just means the event is already gone —
            # not worth alarming about, but still worth a log line.
            print(f"[google calendar error] {method} {path} -> {resp.status_code} {resp.text}")
            return None
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()
    except Exception as e:
        print(f"[google calendar error] {e}")
        return None


def _event_body(booking: dict, room_name: str) -> dict:
    start = booking["start_time"]
    end = booking["end_time"]
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    summary = f"{room_name} — {booking.get('congregation') or booking.get('requester_name', '')}"
    description_lines = [
        f"Booked by: {booking.get('requester_name', '')}",
        f"Congregation: {booking.get('congregation', '')}",
        f"Purpose: {booking.get('purpose', '')}",
        f"Attendance: {booking.get('headcount', '')}",
    ]
    if booking.get("notes"):
        description_lines.append(f"Notes: {booking['notes']}")
    booking_id = booking.get("_id") or booking.get("id") or ""
    return {
        "summary": summary,
        "description": "\n".join(description_lines),
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "extendedProperties": {
            "private": {
                EXT_PROP_KEY: "true",
                "booking_id": str(booking_id),
            }
        },
    }


async def create_event(booking: dict, room_name: str) -> Optional[str]:
    """Creates a calendar event for a newly-approved booking. Returns the
    Google event id (to be saved back onto the booking doc), or None if
    sync is disabled or the call failed."""
    if not _enabled():
        print("[google calendar skipped - not configured]")
        return None
    result = await _request(
        "POST", f"/calendars/{settings.google_calendar_id}/events", json=_event_body(booking, room_name)
    )
    return result.get("id") if result else None


async def update_event(event_id: str, booking: dict, room_name: str) -> None:
    """Updates an already-synced booking's event (time/room/details changed)."""
    if not _enabled() or not event_id:
        return
    await _request(
        "PATCH",
        f"/calendars/{settings.google_calendar_id}/events/{event_id}",
        json=_event_body(booking, room_name),
    )


async def delete_event(event_id: str) -> None:
    """Removes a booking's event (cancelled, rejected, or deleted)."""
    if not _enabled() or not event_id:
        return
    await _request("DELETE", f"/calendars/{settings.google_calendar_id}/events/{event_id}")


def _parse_gcal_datetime(node: dict) -> datetime:
    if "dateTime" in node:
        s = node["dateTime"]
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    # All-day event — only a "date" (YYYY-MM-DD), no time component.
    d = date.fromisoformat(node["date"])
    return datetime.combine(d, time.min)


async def list_external_events(start_after: datetime, start_before: datetime) -> list[dict]:
    """
    Events already on the church calendar that this app did NOT create —
    lets the booker/admin calendar views show existing church events
    (services, external bookings, etc.) without duplicating the ones this
    app already pushed there itself (those are filtered out here since
    they're already shown from our own booking records).
    """
    if not _enabled():
        return []
    time_min = start_after if start_after.tzinfo else start_after.replace(tzinfo=timezone.utc)
    time_max = start_before if start_before.tzinfo else start_before.replace(tzinfo=timezone.utc)
    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
    }
    result = await _request("GET", f"/calendars/{settings.google_calendar_id}/events", params=params)
    if not result:
        return []
    events = []
    for item in result.get("items", []):
        ext = (item.get("extendedProperties") or {}).get("private") or {}
        if ext.get(EXT_PROP_KEY) == "true":
            continue  # our own pushed booking — already represented via the DB
        start = item.get("start") or {}
        end = item.get("end") or {}
        if not start or not end:
            continue
        try:
            events.append(
                {
                    "title": item.get("summary") or "(Untitled event)",
                    "start_time": _parse_gcal_datetime(start),
                    "end_time": _parse_gcal_datetime(end),
                }
            )
        except Exception:
            continue
    return events
