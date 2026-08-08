from datetime import datetime, timedelta

from app.config import settings
from tests.conftest import make_room


async def _admin_token(client):
    await client.post(
        "/api/admin/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "hunter22",
            "setup_secret": settings.admin_setup_secret,
        },
    )
    login = await client.post(
        "/api/admin/login", json={"email": "alice@example.com", "password": "hunter22"}
    )
    return login.json()["access_token"]


def _admin_booking_payload(room_id, start, end, **overrides):
    payload = {
        "room_id": room_id,
        "requester_name": "Church Office",
        "congregation": "Durbanville AM",
        "email": "office@example.com",
        "phone": "+10000000000",
        "headcount": 20,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "purpose": "Sunday service",
        "is_private_event": False,
    }
    payload.update(overrides)
    return payload


async def test_single_admin_booking_is_auto_approved_with_no_series(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    start = datetime.utcnow() + timedelta(days=60)  # far outside the auto-approve window
    end = start + timedelta(hours=1)

    resp = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(room_id, start, end),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1
    assert body["series_id"] is None
    assert body["bookings"][0]["status"] == "approved"


async def test_weekly_recurrence_generates_correct_dates(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    start = datetime(2026, 8, 16, 8, 0)  # a Sunday
    end = start + timedelta(hours=1, minutes=30)

    resp = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start, end,
            recurrence={"frequency": "weekly", "until": "2026-09-13T00:00:00"},
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 5
    assert body["series_id"] is not None

    dates = sorted(b["start_time"][:10] for b in body["bookings"])
    assert dates == ["2026-08-16", "2026-08-23", "2026-08-30", "2026-09-06", "2026-09-13"]
    assert all(b["series_id"] == body["series_id"] for b in body["bookings"])
    # duration preserved on every occurrence
    for b in body["bookings"]:
        s = datetime.fromisoformat(b["start_time"])
        e = datetime.fromisoformat(b["end_time"])
        assert e - s == timedelta(hours=1, minutes=30)


async def test_biweekly_recurrence_generates_correct_dates(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    start = datetime(2026, 8, 16, 8, 0)
    end = start + timedelta(hours=1)

    resp = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start, end,
            recurrence={"frequency": "biweekly", "until": "2026-09-27T00:00:00"},
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    dates = sorted(b["start_time"][:10] for b in resp.json()["bookings"])
    assert dates == ["2026-08-16", "2026-08-30", "2026-09-13", "2026-09-27"]


async def test_monthly_recurrence_handles_month_length_overflow(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    # 31st doesn't exist in every following month — should clamp, not crash
    start = datetime(2026, 1, 31, 9, 0)
    end = start + timedelta(hours=1)

    resp = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start, end,
            recurrence={"frequency": "monthly", "until": "2026-04-30T00:00:00"},
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    dates = sorted(b["start_time"][:10] for b in resp.json()["bookings"])
    assert dates == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]


async def test_recurring_conflict_blocks_entire_series(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime(2026, 8, 16, 8, 0)
    end = start + timedelta(hours=1)

    first = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start, end,
            recurrence={"frequency": "weekly", "until": "2026-08-30T00:00:00"},
        ),
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["created_count"] == 3

    # A second series that overlaps one of those Sundays should be rejected
    # entirely — nothing from it should be created.
    conflicting = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start + timedelta(minutes=30), end + timedelta(minutes=30),
            recurrence={"frequency": "weekly", "until": "2026-08-30T00:00:00"},
        ),
        headers=headers,
    )
    assert conflicting.status_code == 409

    all_bookings = await client.get("/api/bookings", params={"room_id": room_id})
    assert len(all_bookings.json()) == 3  # only the first series exists


async def test_cancel_series_cancels_every_occurrence(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime(2026, 8, 16, 8, 0)
    end = start + timedelta(hours=1)

    created = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start, end,
            recurrence={"frequency": "weekly", "until": "2026-08-30T00:00:00"},
        ),
        headers=headers,
    )
    series_id = created.json()["series_id"]
    assert created.json()["created_count"] == 3

    cancelled = await client.post(f"/api/admin/bookings/series/{series_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled_count"] == 3

    all_bookings = await client.get("/api/bookings", params={"room_id": room_id})
    assert all(b["status"] == "cancelled" for b in all_bookings.json())


async def test_admin_single_cancel_does_not_need_email(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime.utcnow() + timedelta(days=5)
    end = start + timedelta(hours=1)

    created = await client.post(
        "/api/admin/bookings", json=_admin_booking_payload(room_id, start, end), headers=headers
    )
    booking_id = created.json()["bookings"][0]["id"]

    cancelled = await client.post(f"/api/admin/bookings/{booking_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_admin_booking_creation_requires_admin_auth(client, rooms_col):
    room_id = await make_room(rooms_col)
    start = datetime.utcnow() + timedelta(days=5)
    end = start + timedelta(hours=1)
    resp = await client.post("/api/admin/bookings", json=_admin_booking_payload(room_id, start, end))
    assert resp.status_code == 401


async def test_excessive_recurrence_range_is_rejected(client, rooms_col):
    room_id = await make_room(rooms_col)
    token = await _admin_token(client)
    start = datetime(2026, 1, 1, 8, 0)
    end = start + timedelta(hours=1)

    resp = await client.post(
        "/api/admin/bookings",
        json=_admin_booking_payload(
            room_id, start, end,
            # ~3 years weekly — well past the 104-occurrence cap
            recurrence={"frequency": "weekly", "until": "2029-01-01T00:00:00"},
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
