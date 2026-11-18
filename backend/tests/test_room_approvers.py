import pytest

from app import notifications
from app.config import settings
from tests.conftest import make_room
from tests.test_calendar_sync import _make_admin
from tests.test_private_link import URL, body

OFFICE = "+27821111111"


@pytest.fixture
def alerts(monkeypatch):
    """Records (number, template, room name) for every WhatsApp the system tries to send."""
    sent = []

    async def fake_whatsapp(phone, template, params):
        sent.append((phone, template, params[2]))

    async def fake_email(*args, **kwargs):
        return None

    monkeypatch.setattr(notifications, "send_whatsapp", fake_whatsapp)
    monkeypatch.setattr(notifications, "send_email", fake_email)
    monkeypatch.setattr(settings, "admin_notify_whatsapp", OFFICE)
    return sent


async def set_approvers(client, admin, room_id, numbers):
    return await client.put(f"/api/admin/room-approvers/{room_id}", json={"numbers": numbers}, headers=admin)


async def request_room(client, room_id, email="thandi@example.com"):
    resp = await client.post(URL, json=body(room_id, email=email, phone="+27 82 000 0000"))
    assert resp.status_code == 200, resp.text


async def test_a_room_with_approvers_alerts_only_them(client, rooms_col, alerts):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    resp = await set_approvers(client, admin, hall, ["082 222 3333", "+27 83 444 5555"])
    assert resp.status_code == 200 and resp.json()["numbers"] == ["+27822223333", "+27834445555"]

    await request_room(client, hall)
    assert sorted(a[0] for a in alerts if a[1] == "admin_new_request") == ["+27822223333", "+27834445555"]


async def test_a_room_without_approvers_falls_back_to_the_office_number(client, rooms_col, alerts):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await request_room(client, hall)
    assert [a[0] for a in alerts if a[1] == "admin_new_request"] == [OFFICE]


async def test_each_room_alerts_its_own_people(client, rooms_col, alerts):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    kids = await make_room(rooms_col, name="Kids 1", capacity=100)
    await set_approvers(client, admin, hall, ["+27820000001"])
    await set_approvers(client, admin, kids, ["+27820000002"])

    await request_room(client, hall)
    await request_room(client, kids, email="other@example.com")
    got = {(a[0], a[2]) for a in alerts if a[1] == "admin_new_request"}
    assert got == {("+27820000001", "Main Hall"), ("+27820000002", "Kids 1")}


async def test_clearing_the_numbers_goes_back_to_the_office(client, rooms_col, alerts):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await set_approvers(client, admin, hall, ["+27820000001"])
    cleared = await set_approvers(client, admin, hall, [])
    assert cleared.status_code == 200 and cleared.json()["numbers"] == []
    assert (await client.get("/api/admin/room-approvers", headers=admin)).json() == {}

    await request_room(client, hall)
    assert [a[0] for a in alerts if a[1] == "admin_new_request"] == [OFFICE]


async def test_a_person_is_alerted_once_however_the_number_is_written():
    room = {"name": "X", "approval_whatsapp": ["+27 82 111 1111", "0821111111", "+27821111111"]}
    assert notifications.admin_whatsapp_targets(room) == ["+27 82 111 1111"]


async def test_office_list_is_deduplicated_too(monkeypatch):
    monkeypatch.setattr(settings, "admin_notify_whatsapp", "0821111111, +27821111111 ,, 0832222222")
    assert notifications.admin_whatsapp_targets({"name": "X"}) == ["0821111111", "0832222222"]


async def test_bad_numbers_are_refused_and_nothing_is_saved(client, rooms_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    resp = await set_approvers(client, admin, hall, ["+27820000001", "not a number"])
    assert resp.status_code == 400 and "not a number" in resp.json()["detail"]
    assert (await client.get("/api/admin/room-approvers", headers=admin)).json() == {}

    too_many = await set_approvers(client, admin, hall, [f"08200000{i:02d}" for i in range(11)])
    assert too_many.status_code == 400 and "At most 10" in too_many.json()["detail"]


async def test_unknown_room_is_a_404(client):
    admin = await _make_admin(client)
    assert (await set_approvers(client, admin, "64b000000000000000000000", ["+27820000001"])).status_code == 404
    assert (await set_approvers(client, admin, "nope", ["+27820000001"])).status_code == 404


async def test_only_admins_can_see_or_set_approvers(client, rooms_col):
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    assert (await client.get("/api/admin/room-approvers")).status_code in (401, 403)
    assert (await client.put(f"/api/admin/room-approvers/{hall}", json={"numbers": ["+27820000001"]})).status_code in (401, 403)


async def test_the_numbers_never_leak_through_the_public_room_list(client, rooms_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Main Hall", capacity=300)
    await set_approvers(client, admin, hall, ["+27820000001"])
    listing = await client.get("/api/rooms")
    assert listing.status_code == 200
    assert "27820000001" not in listing.text and "approval_whatsapp" not in listing.text
