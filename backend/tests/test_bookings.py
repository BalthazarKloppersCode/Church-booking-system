import pytest

from tests.conftest import booking_payload, make_room


async def test_booking_within_auto_approve_window_is_approved(client, rooms_col):
    room_id = await make_room(rooms_col)
    resp = await client.post("/api/bookings", json=booking_payload(room_id, start_offset_days=3))
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_booking_response_times_are_explicitly_utc(client, rooms_col):
    """
    `new Date(...)` on the frontend treats a timezone-less ISO string as
    local time, not UTC — the API must always say "+00:00"/"Z" explicitly
    so the browser doesn't silently shift every displayed time.
    """
    room_id = await make_room(rooms_col)
    resp = await client.post("/api/bookings", json=booking_payload(room_id))
    body = resp.json()
    for field in ("start_time", "end_time", "created_at", "updated_at"):
        value = body[field]
        assert value.endswith("+00:00") or value.endswith("Z"), (
            f"{field}={value!r} has no UTC marker — frontend Date parsing will misinterpret it as local time"
        )


async def test_booking_accepts_timezone_aware_timestamps_from_browser(client, rooms_col):
    """
    Browsers send Date.toISOString() output, which is timezone-aware (ends
    in "Z"), not the naive timestamps our own test helper builds. This must
    not crash comparing against datetime.utcnow().
    """
    from datetime import datetime, timedelta, timezone

    room_id = await make_room(rooms_col)
    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=2)
    resp = await client.post(
        "/api/bookings",
        json=booking_payload(
            room_id,
            start_time=start.isoformat().replace("+00:00", "Z"),
            end_time=end.isoformat().replace("+00:00", "Z"),
        ),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_booking_beyond_auto_approve_window_needs_approval(client, rooms_col):
    room_id = await make_room(rooms_col)
    resp = await client.post("/api/bookings", json=booking_payload(room_id, start_offset_days=20))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_private_event_always_needs_approval_even_if_soon(client, rooms_col):
    room_id = await make_room(rooms_col)
    resp = await client.post(
        "/api/bookings",
        json=booking_payload(room_id, start_offset_days=1, is_private_event=True),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_booking_over_capacity_is_rejected(client, rooms_col):
    room_id = await make_room(rooms_col, capacity=10)
    resp = await client.post("/api/bookings", json=booking_payload(room_id, headcount=50))
    assert resp.status_code == 400


async def test_overlapping_booking_conflict(client, rooms_col):
    room_id = await make_room(rooms_col)
    first = booking_payload(room_id, start_offset_days=5, duration_hours=3)
    resp1 = await client.post("/api/bookings", json=first)
    assert resp1.status_code == 200

    second = booking_payload(room_id, start_offset_days=5, duration_hours=3)
    resp2 = await client.post("/api/bookings", json=second)
    assert resp2.status_code == 409


async def test_non_overlapping_booking_succeeds(client, rooms_col):
    room_id = await make_room(rooms_col)
    resp1 = await client.post(
        "/api/bookings", json=booking_payload(room_id, start_offset_days=5, duration_hours=1)
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/api/bookings",
        json=booking_payload(
            room_id,
            start_offset_days=5,
            duration_hours=1,
            start_time=resp1.json()["end_time"],
        ),
    )
    assert resp2.status_code == 200


async def test_booking_missing_room_404s(client):
    from bson import ObjectId

    resp = await client.post("/api/bookings", json=booking_payload(str(ObjectId())))
    assert resp.status_code == 404


async def test_cancel_requires_matching_email(client, rooms_col):
    room_id = await make_room(rooms_col)
    created = (await client.post("/api/bookings", json=booking_payload(room_id))).json()

    wrong_email = await client.post(
        f"/api/bookings/{created['id']}/cancel", params={"email": "someone-else@example.com"}
    )
    assert wrong_email.status_code == 403

    right_email = await client.post(
        f"/api/bookings/{created['id']}/cancel", params={"email": created["email"]}
    )
    assert right_email.status_code == 200
    assert right_email.json()["status"] == "cancelled"


async def test_list_bookings_filters_by_email(client, rooms_col):
    room_id = await make_room(rooms_col)
    await client.post("/api/bookings", json=booking_payload(room_id, email="a@example.com"))
    await client.post(
        "/api/bookings", json=booking_payload(room_id, email="b@example.com", start_offset_days=6)
    )

    resp = await client.get("/api/bookings", params={"email": "a@example.com"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["email"] == "a@example.com"
