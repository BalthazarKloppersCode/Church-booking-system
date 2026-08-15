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


async def _make_area(client, headers, **overrides):
    payload = {"name": "Northern Hub", "requires_login": False, "always_requires_approval": False}
    payload.update(overrides)
    resp = await client.post("/api/areas", json=payload, headers=headers)
    return resp.json()["id"]


async def _make_congregation(client, headers, area_id, name="Durbanville AM"):
    resp = await client.post(
        "/api/congregations", json={"name": name, "area_id": area_id}, headers=headers
    )
    return resp.json()


async def test_booking_for_login_required_area_rejected_without_token(client, rooms_col):
    admin_token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}
    area_id = await _make_area(client, headers, name="Northern Hub", requires_login=True)
    await _make_congregation(client, headers, area_id, "Durbanville AM")
    room_id = await make_room(rooms_col)

    resp = await client.post(
        "/api/bookings", json=booking_payload(room_id, congregation="Durbanville AM")
    )
    assert resp.status_code == 403


async def test_booking_for_login_required_area_succeeds_when_logged_in(client, rooms_col):
    admin_token = await _admin_token(client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    area_id = await _make_area(client, admin_headers, name="Northern Hub", requires_login=True)
    await _make_congregation(client, admin_headers, area_id, "Durbanville AM")
    room_id = await make_room(rooms_col)

    created_user = await client.post(
        "/api/admin/users",
        json={"name": "Booker", "email": "booker@example.com", "phone": "+10000000000", "password": "letmein1"},
        headers=admin_headers,
    )
    assert created_user.status_code == 200

    login = await client.post(
        "/api/auth/login", json={"email": "booker@example.com", "password": "letmein1"}
    )
    assert login.status_code == 200
    user_token = login.json()["access_token"]

    resp = await client.post(
        "/api/bookings",
        json=booking_payload(room_id, congregation="Durbanville AM", start_offset_days=3),
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_area_always_requires_approval_overrides_two_week_window(client, rooms_col):
    admin_token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}
    area_id = await _make_area(
        client, headers, name="Joshua Generation City", requires_login=False, always_requires_approval=True
    )
    await _make_congregation(client, headers, area_id, "JGC Main")
    room_id = await make_room(rooms_col)

    # Even though this is well within the 2-week auto-approve window, the
    # area's always_requires_approval flag must force it to pending.
    resp = await client.post(
        "/api/bookings",
        json=booking_payload(room_id, congregation="JGC Main", start_offset_days=2),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_congregation_with_no_area_keeps_default_two_week_rule(client, rooms_col):
    room_id = await make_room(rooms_col)
    resp = await client.post(
        "/api/bookings",
        json=booking_payload(room_id, congregation="Unlisted Group", start_offset_days=2),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_admin_can_manage_users(client):
    admin_token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    created = await client.post(
        "/api/admin/users",
        json={"name": "Booker", "email": "booker@example.com", "phone": "+1000", "password": "letmein1"},
        headers=headers,
    )
    assert created.status_code == 200
    assert "password" not in created.json()
    assert "password_hash" not in created.json()
    user_id = created.json()["id"]

    listed = await client.get("/api/admin/users", headers=headers)
    assert listed.status_code == 200
    assert any(u["id"] == user_id for u in listed.json())

    updated = await client.patch(
        f"/api/admin/users/{user_id}", json={"phone": "+2000"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+2000"

    deleted = await client.delete(f"/api/admin/users/{user_id}", headers=headers)
    assert deleted.status_code == 200
    listed_after = await client.get("/api/admin/users", headers=headers)
    assert not any(u["id"] == user_id for u in listed_after.json())


async def test_manage_users_requires_admin_auth(client):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


async def test_booker_login_rejects_wrong_password(client):
    admin_token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post(
        "/api/admin/users",
        json={"name": "Booker", "email": "booker@example.com", "phone": "+1000", "password": "letmein1"},
        headers=headers,
    )
    resp = await client.post(
        "/api/auth/login", json={"email": "booker@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_user_token_cannot_access_admin_routes(client):
    admin_token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post(
        "/api/admin/users",
        json={"name": "Booker", "email": "booker@example.com", "phone": "+1000", "password": "letmein1"},
        headers=headers,
    )
    login = await client.post(
        "/api/auth/login", json={"email": "booker@example.com", "password": "letmein1"}
    )
    user_token = login.json()["access_token"]

    resp = await client.get(
        "/api/admin/dashboard", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 401


async def test_admin_can_edit_and_delete_any_booking(client, rooms_col):
    room_id = await make_room(rooms_col)
    booking = await client.post("/api/bookings", json=booking_payload(room_id))
    booking_id = booking.json()["id"]

    admin_token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    edited = await client.patch(
        f"/api/admin/bookings/{booking_id}", json={"headcount": 99}, headers=headers
    )
    assert edited.status_code == 200
    assert edited.json()["headcount"] == 99

    deleted = await client.delete(f"/api/admin/bookings/{booking_id}", headers=headers)
    assert deleted.status_code == 200

    all_bookings = await client.get("/api/bookings")
    assert not any(b["id"] == booking_id for b in all_bookings.json())
