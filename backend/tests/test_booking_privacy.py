import pytest
from bson import ObjectId

from app.auth import create_user_access_token
from tests.conftest import booking_payload, make_room
from tests.test_calendar_sync import _make_admin

PERSONAL = {"email", "phone", "requester_name", "congregation", "headcount", "notes", "created_by", "google_event_id"}


async def book(client, room_id, headers, **overrides):
    resp = await client.post("/api/bookings", json=booking_payload(room_id, **overrides), headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def reference_of(booking):
    return "JGP-" + booking["id"][-8:].upper()


# ---------- the full list is for the office only ----------


async def test_the_full_list_is_closed_to_the_public_and_to_bookers(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    await book(client, room, booker_headers, requester_name="Secret Person", phone="+27 82 000 1111")

    assert (await client.get("/api/bookings")).status_code == 401
    assert (await client.get("/api/bookings", params={"email": "jane@example.com"})).status_code == 401
    assert (await client.get("/api/bookings", headers=booker_headers)).status_code == 401  # a booker is not an admin


async def test_the_office_still_sees_everything(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    await book(client, room, booker_headers, requester_name="Secret Person")
    admin = await _make_admin(client)
    rows = (await client.get("/api/bookings", headers=admin)).json()
    assert rows[0]["requester_name"] == "Secret Person" and rows[0]["email"] == "jane@example.com"


async def test_the_public_calendar_still_works_and_shows_no_personal_details(client, rooms_col, booker_headers):
    room = await make_room(rooms_col, name="Calendar Room")
    await book(client, room, booker_headers, requester_name="Secret Person")
    entries = (await client.get("/api/bookings/calendar")).json()
    assert entries and not (PERSONAL & set(entries[0].keys()))


# ---------- find by email + reference (no account) ----------


async def test_a_booking_is_found_with_its_email_and_reference(client, rooms_col, booker_headers):
    room = await make_room(rooms_col, name="Hall")
    made = await book(client, room, booker_headers)
    resp = await client.post("/api/bookings/find", json={"email": "jane@example.com", "reference": reference_of(made)})
    assert resp.status_code == 200
    found = resp.json()
    assert [b["id"] for b in found] == [made["id"]] and found[0]["reference"] == reference_of(made)
    assert found[0]["room_name"] == "Hall" and found[0]["status"] in ("pending", "approved")
    assert not (PERSONAL & set(found[0].keys()))  # nothing about the requester comes back


async def test_the_reference_is_forgiving_about_how_it_is_typed(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    made = await book(client, room, booker_headers)
    suffix = made["id"][-8:]
    for typed in (reference_of(made).lower(), suffix.upper(), f" jgp {suffix.lower()} ", f"JGP{suffix.upper()}"):
        resp = await client.post("/api/bookings/find", json={"email": "JANE@Example.com", "reference": typed})
        assert resp.status_code == 200, typed


async def test_an_email_alone_or_a_wrong_half_reveals_nothing(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    made = await book(client, room, booker_headers)
    wrong_email = await client.post("/api/bookings/find", json={"email": "stranger@example.com", "reference": reference_of(made)})
    wrong_ref = await client.post("/api/bookings/find", json={"email": "jane@example.com", "reference": "JGP-00000000"})
    short_ref = await client.post("/api/bookings/find", json={"email": "jane@example.com", "reference": "JGP-" + made["id"][-4:]})
    assert wrong_email.status_code == wrong_ref.status_code == short_ref.status_code == 404
    assert wrong_email.json() == wrong_ref.json() == short_ref.json()  # the same answer, so neither half can be probed


async def test_one_persons_reference_does_not_open_someone_elses_booking(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    mine = await book(client, room, booker_headers, email="a@example.com")
    theirs = await book(client, room, booker_headers, email="b@example.com", start_offset_days=6)
    resp = await client.post("/api/bookings/find", json={"email": "a@example.com", "reference": reference_of(theirs)})
    assert resp.status_code == 404
    ok = await client.post("/api/bookings/find", json={"email": "a@example.com", "reference": reference_of(mine)})
    assert [b["id"] for b in ok.json()] == [mine["id"]]


async def test_a_special_character_email_does_not_act_as_a_pattern(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    made = await book(client, room, booker_headers, email="plus+tag@example.com")
    assert (await client.post("/api/bookings/find", json={"email": "plus+tag@example.com", "reference": reference_of(made)})).status_code == 200
    assert (await client.post("/api/bookings/find", json={"email": "plustag@example.com", "reference": reference_of(made)})).status_code == 404


# ---------- a logged-in booker's own bookings ----------


async def test_a_logged_in_booker_sees_only_their_own_bookings(client, rooms_col, booker_headers, app_state):
    room = await make_room(rooms_col)
    mine = await book(client, room, booker_headers, email="booker@example.com")  # made with their own email
    made_for_someone = await book(client, room, booker_headers, email="host@example.com", start_offset_days=6)  # made for a host
    other = await app_state["users"].insert_one({"name": "Other", "email": "other@example.com", "phone": "+2700", "active": True, "password_hash": "x"})
    other_headers = {"Authorization": f"Bearer {create_user_access_token(str(other.inserted_id))}"}
    theirs = await book(client, room, other_headers, email="other@example.com", start_offset_days=7)

    mine_list = (await client.get("/api/bookings/mine", headers=booker_headers)).json()
    assert {b["id"] for b in mine_list} == {mine["id"], made_for_someone["id"]}
    assert theirs["id"] not in {b["id"] for b in mine_list}
    assert not (PERSONAL & set(mine_list[0].keys()))
    assert (await client.get("/api/bookings/mine")).status_code == 401


async def test_bookings_with_the_accounts_email_show_up_even_if_made_by_the_office(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    admin = await _make_admin(client)
    from datetime import datetime, timedelta

    start = datetime.utcnow() + timedelta(days=9)
    resp = await client.post(
        "/api/admin/bookings",
        json={"room_id": room, "requester_name": "Booker", "congregation": "Youth Group", "email": "booker@example.com", "phone": "+2700000",
              "headcount": 5, "purpose": "Bible study", "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat()},
        headers=admin,
    )
    assert resp.status_code == 200
    mine = (await client.get("/api/bookings/mine", headers=booker_headers)).json()
    assert len(mine) == 1


# ---------- confirmation and cancel: email, or being the booker ----------


async def test_the_booker_can_view_and_cancel_a_booking_made_for_someone_else_without_an_email(client, rooms_col, booker_headers):
    room = await make_room(rooms_col)
    made = await book(client, room, booker_headers, email="host@example.com")

    # Nobody else, and nobody with no proof, gets in.
    assert (await client.get(f"/api/bookings/{made['id']}/confirmation")).status_code == 403
    assert (await client.get(f"/api/bookings/{made['id']}/confirmation", params={"email": "x@example.com"})).status_code == 403

    assert (await client.get(f"/api/bookings/{made['id']}/confirmation", headers=booker_headers)).status_code == 200
    assert (await client.post(f"/api/bookings/{made['id']}/cancel")).status_code == 403
    cancelled = await client.post(f"/api/bookings/{made['id']}/cancel", headers=booker_headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


async def test_another_logged_in_booker_cannot_touch_it(client, rooms_col, booker_headers, app_state):
    room = await make_room(rooms_col)
    made = await book(client, room, booker_headers, email="host@example.com")
    other = await app_state["users"].insert_one({"name": "Other", "email": "other@example.com", "phone": "+2700", "active": True, "password_hash": "x"})
    other_headers = {"Authorization": f"Bearer {create_user_access_token(str(other.inserted_id))}"}
    assert (await client.get(f"/api/bookings/{made['id']}/confirmation", headers=other_headers)).status_code == 403
    assert (await client.post(f"/api/bookings/{made['id']}/cancel", headers=other_headers)).status_code == 403


async def test_a_missing_or_malformed_id_is_a_clean_404(client):
    assert (await client.post(f"/api/bookings/{ObjectId()}/cancel", params={"email": "a@example.com"})).status_code == 404
    assert (await client.post("/api/bookings/not-an-id/cancel", params={"email": "a@example.com"})).status_code == 404
