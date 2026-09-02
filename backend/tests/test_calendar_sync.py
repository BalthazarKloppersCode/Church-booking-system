from datetime import datetime, timedelta

from bson import ObjectId

from app import google_calendar
from tests.conftest import booking_payload, make_room


async def _make_admin(client):
    await client.post(
        "/api/admin/register",
        json={
            "name": "Admin",
            "email": "admin@example.com",
            "password": "secret123",
            "setup_secret": "test-setup-secret",
        },
    )
    resp = await client.post("/api/admin/login", json={"email": "admin@example.com", "password": "secret123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_approving_booking_pushes_a_google_event_and_saves_its_id(
    client, rooms_col, bookings_col, booker_headers, monkeypatch
):
    async def _fake_create(booking, room_name):
        return "gcal-event-123"

    monkeypatch.setattr(google_calendar, "create_event", _fake_create)

    room_id = await make_room(rooms_col)
    created = await client.post(
        "/api/bookings",
        json=booking_payload(room_id, start_offset_days=20),  # beyond auto-approve window -> pending
        headers=booker_headers,
    )
    assert created.json()["status"] == "pending"

    admin_headers = await _make_admin(client)
    approved = await client.post(
        f"/api/admin/bookings/{created.json()['id']}/approve", json={}, headers=admin_headers
    )
    assert approved.status_code == 200

    stored = await bookings_col.find_one({"_id": ObjectId(created.json()["id"])})
    assert stored["google_event_id"] == "gcal-event-123"


async def test_cancelling_synced_booking_deletes_its_google_event(
    client, rooms_col, bookings_col, booker_headers, monkeypatch
):
    deleted_ids = []

    async def _fake_delete(event_id):
        deleted_ids.append(event_id)

    monkeypatch.setattr(google_calendar, "delete_event", _fake_delete)

    room_id = await make_room(rooms_col)
    created = (
        await client.post("/api/bookings", json=booking_payload(room_id), headers=booker_headers)
    ).json()
    await bookings_col.update_one({"_id": ObjectId(created["id"])}, {"$set": {"google_event_id": "gcal-abc"}})

    resp = await client.post(
        f"/api/bookings/{created['id']}/cancel", params={"email": created["email"]}
    )
    assert resp.status_code == 200
    assert deleted_ids == ["gcal-abc"]


async def test_admin_cancelling_series_deletes_every_synced_event(client, rooms_col, bookings_col, monkeypatch):
    deleted_ids = []

    async def _fake_delete(event_id):
        deleted_ids.append(event_id)

    monkeypatch.setattr(google_calendar, "delete_event", _fake_delete)

    admin_headers = await _make_admin(client)
    room_id = await make_room(rooms_col)
    start = datetime.utcnow() + timedelta(days=5)
    created = await client.post(
        "/api/admin/bookings",
        json={
            "room_id": room_id,
            "requester_name": "Jane",
            "congregation": "Youth",
            "email": "jane@example.com",
            "phone": "+10000000000",
            "headcount": 5,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
            "purpose": "Bible study",
            "recurrence": {"frequency": "weekly", "until": (start + timedelta(days=21)).isoformat()},
        },
        headers=admin_headers,
    )
    body = created.json()
    series_id = body["series_id"]
    # Pretend two of the occurrences already synced to Google before cancelling.
    ids = [b["id"] for b in body["bookings"]]
    for bid, event_id in zip(ids[:2], ["gcal-1", "gcal-2"]):
        await bookings_col.update_one({"_id": ObjectId(bid)}, {"$set": {"google_event_id": event_id}})

    resp = await client.post(f"/api/admin/bookings/series/{series_id}/cancel", headers=admin_headers)
    assert resp.status_code == 200
    assert sorted(deleted_ids) == ["gcal-1", "gcal-2"]


async def test_external_calendar_events_empty_when_sync_not_configured(client):
    resp = await client.get("/api/bookings/calendar/external")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_external_calendar_events_returned_when_configured(client, monkeypatch):
    async def _fake_list(start_after, start_before):
        return [
            {
                "title": "Sunday Service",
                "start_time": datetime(2026, 1, 4, 9, 0),
                "end_time": datetime(2026, 1, 4, 11, 0),
            }
        ]

    monkeypatch.setattr(google_calendar, "list_external_events", _fake_list)

    resp = await client.get("/api/bookings/calendar/external")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["title"] == "Sunday Service"
