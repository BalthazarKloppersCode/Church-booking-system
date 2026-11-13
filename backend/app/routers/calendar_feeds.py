"""
The extra Google calendars the office adds (admin only).

Each one is a name plus the calendar's "secret address in iCal format". The address
is a secret (it lets anyone read the whole calendar), so it is stored on the server
and never sent back: the list only shows where it points and the last few characters.
"""
from datetime import datetime
from urllib.parse import urlparse

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app import ical_feed
from app.auth import get_current_admin
from app.config import settings
from app.database import calendar_feeds_collection
from app.models import CalendarFeedCreate, CalendarFeedUpdate

router = APIRouter(prefix="/api/admin/calendar-feeds", tags=["calendar-feeds"])

MAX_FEEDS = 25


def _hint(url: str) -> str:
    return f"{urlparse(url).hostname} · …{url[-8:]}"


async def _describe(doc: dict) -> dict:
    status = await ical_feed.feed_status(doc["url"]) if doc.get("enabled", True) else {"ok": True, "error": None, "upcoming": 0}
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "enabled": doc.get("enabled", True),
        "link_hint": _hint(doc["url"]),
        "ok": status["ok"],
        "error": status["error"],
        "upcoming": status["upcoming"],
    }


@router.get("")
async def list_feeds(admin=Depends(get_current_admin)):
    feeds = []
    if ical_feed.legacy_enabled():
        url = settings.google_calendar_ical_url.strip()
        status = await ical_feed.feed_status(url)
        feeds.append(
            {
                "id": None, "name": ical_feed.LEGACY_NAME, "enabled": True, "built_in": True,
                "link_hint": "set in the server settings", "ok": status["ok"], "error": status["error"], "upcoming": status["upcoming"],
            }
        )
    docs = [d async for d in calendar_feeds_collection.find({}).sort("created_at", 1)]
    for doc in docs:
        feeds.append(await _describe(doc))
    return feeds


@router.post("")
async def add_feed(payload: CalendarFeedCreate, admin=Depends(get_current_admin)):
    try:
        url = ical_feed.normalize_url(payload.url)
    except ical_feed.FeedError as e:
        raise HTTPException(400, str(e))
    if await calendar_feeds_collection.count_documents({}) >= MAX_FEEDS:
        raise HTTPException(400, f"You can add up to {MAX_FEEDS} calendars")
    if await calendar_feeds_collection.find_one({"url": url}) or url == settings.google_calendar_ical_url.strip():
        raise HTTPException(400, "That calendar has already been added")

    # Check it really is a calendar before saving, so a typo is caught now and not later.
    calendar, error = await ical_feed.fetch_calendar(url)
    if calendar is None:
        raise HTTPException(400, f"Couldn't use that link: {error}")

    doc = {"name": payload.name.strip(), "url": url, "enabled": True, "created_at": datetime.utcnow()}
    result = await calendar_feeds_collection.insert_one(doc)
    ical_feed.remember(url, calendar)
    return await _describe({**doc, "_id": result.inserted_id})


@router.patch("/{feed_id}")
async def update_feed(feed_id: str, payload: CalendarFeedUpdate, admin=Depends(get_current_admin)):
    doc = await calendar_feeds_collection.find_one({"_id": ObjectId(feed_id)}) if ObjectId.is_valid(feed_id) else None
    if not doc:
        raise HTTPException(404, "Calendar not found")
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if changes:
        await calendar_feeds_collection.update_one({"_id": doc["_id"]}, {"$set": changes})
    return await _describe({**doc, **changes})


@router.delete("/{feed_id}")
async def delete_feed(feed_id: str, admin=Depends(get_current_admin)):
    doc = await calendar_feeds_collection.find_one({"_id": ObjectId(feed_id)}) if ObjectId.is_valid(feed_id) else None
    if not doc:
        raise HTTPException(404, "Calendar not found")
    await calendar_feeds_collection.delete_one({"_id": doc["_id"]})
    ical_feed.forget(doc["url"])
    return {"ok": True}
