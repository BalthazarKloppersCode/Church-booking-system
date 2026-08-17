from app.config import settings
from tests.conftest import booking_payload, make_room


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


async def test_pending_booking_appears_in_approvals_and_can_be_approved(client, rooms_col, booker_headers):
    room_id = await make_room(rooms_col)
    pending = await client.post(
        "/api/bookings", json=booking_payload(room_id, start_offset_days=30), headers=booker_headers
    )
    assert pending.json()["status"] == "pending"
    booking_id = pending.json()["id"]

    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    approvals = await client.get("/api/admin/approvals", headers=headers)
    assert approvals.status_code == 200
    assert any(b["id"] == booking_id for b in approvals.json())

    approved = await client.post(
        f"/api/admin/bookings/{booking_id}/approve", json={"admin_note": "Looks good"}, headers=headers
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["admin_note"] == "Looks good"


async def test_rejecting_a_booking_sets_status_and_note(client, rooms_col, booker_headers):
    room_id = await make_room(rooms_col)
    pending = await client.post(
        "/api/bookings", json=booking_payload(room_id, is_private_event=True), headers=booker_headers
    )
    booking_id = pending.json()["id"]

    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    rejected = await client.post(
        f"/api/admin/bookings/{booking_id}/reject",
        json={"admin_note": "Room unavailable that day"},
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["admin_note"] == "Room unavailable that day"


async def test_approvals_endpoint_requires_admin_auth(client):
    resp = await client.get("/api/admin/approvals")
    assert resp.status_code == 401


async def test_dashboard_counts_pending_and_active_rooms(client, rooms_col, booker_headers):
    room_id = await make_room(rooms_col)
    await client.post(
        "/api/bookings", json=booking_payload(room_id, start_offset_days=30), headers=booker_headers
    )

    token = await _admin_token(client)
    resp = await client.get(
        "/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_approvals"] == 1
    assert data["active_rooms"] == 1
