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


async def test_list_congregations_public_no_auth(client):
    resp = await client.get("/api/congregations")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_congregation_requires_admin(client):
    resp = await client.post("/api/congregations", json={"name": "Youth Group"})
    assert resp.status_code == 401


async def test_create_and_list_congregation(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/congregations", json={"name": "Youth Group"}, headers=headers
    )
    assert created.status_code == 200
    assert created.json()["active"] is True

    listed = await client.get("/api/congregations")
    assert listed.status_code == 200
    names = [c["name"] for c in listed.json()]
    assert "Youth Group" in names


async def test_duplicate_congregation_name_rejected(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/congregations", json={"name": "Youth Group"}, headers=headers)
    dup = await client.post("/api/congregations", json={"name": "Youth Group"}, headers=headers)
    assert dup.status_code == 400


async def test_deactivate_congregation_hides_it_from_default_list(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/congregations", json={"name": "Youth Group"}, headers=headers
    )
    congregation_id = created.json()["id"]

    deactivated = await client.delete(
        f"/api/congregations/{congregation_id}", headers=headers
    )
    assert deactivated.status_code == 200

    active_only = await client.get("/api/congregations")
    assert active_only.json() == []

    including_inactive = await client.get("/api/congregations", params={"active_only": False})
    names = [c["name"] for c in including_inactive.json()]
    assert "Youth Group" in names


async def test_list_bookings_filters_by_congregation(client, rooms_col):
    room_id = await make_room(rooms_col)
    await client.post(
        "/api/bookings", json=booking_payload(room_id, congregation="Youth Group")
    )
    await client.post(
        "/api/bookings",
        json=booking_payload(room_id, congregation="Deacons", start_offset_days=6),
    )

    resp = await client.get("/api/bookings", params={"congregation": "Youth Group"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["congregation"] == "Youth Group"
