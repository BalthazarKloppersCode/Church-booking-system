from datetime import datetime, timedelta

import pytest

from app import notifications, password_reset
from app.auth import create_access_token, create_user_access_token, hash_password
from tests.test_calendar_sync import _make_admin

NEW = "a-brand-new-password"


@pytest.fixture
def whatsapps(monkeypatch):
    sent = []

    async def fake(phone, template, params):
        sent.append((phone, template, params))

    monkeypatch.setattr(notifications, "send_whatsapp", fake)
    return sent


async def make_user(app_state, **overrides):
    doc = {
        "name": "Jane Booker",
        "email": "jane@example.com",
        "phone": "+27821234567",
        "area_id": None,
        "active": True,
        "password_hash": hash_password("old-password-1"),
    }
    doc.update(overrides)
    result = await app_state["users"].insert_one(doc)
    return str(result.inserted_id)


async def ask_for_code(client, whatsapps, email="jane@example.com"):
    resp = await client.post("/api/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    return whatsapps[-1][2][0] if whatsapps else None


async def login(client, password, email="jane@example.com"):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


# ---------- booker: forgot password ----------


async def test_a_code_goes_to_the_whatsapp_number_on_the_account(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)

    phone, template, params = whatsapps[0]
    assert (phone, template) == ("+27821234567", "password_reset")
    assert len(code) == 6 and code.isdigit()
    assert len(whatsapps) == 1


async def test_the_answer_is_the_same_whether_or_not_the_email_is_registered(client, app_state, whatsapps):
    await make_user(app_state)
    known = await client.post("/api/auth/forgot-password", json={"email": "jane@example.com"})
    unknown = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(whatsapps) == 1  # nothing was sent for the unknown email


async def test_nothing_is_sent_for_an_inactive_account_or_one_without_a_phone(client, app_state, whatsapps):
    await make_user(app_state, email="off@example.com", active=False)
    await make_user(app_state, email="nophone@example.com", phone="  ")
    await ask_for_code(client, whatsapps, "off@example.com")
    await ask_for_code(client, whatsapps, "nophone@example.com")
    assert whatsapps == []


async def test_the_code_is_stored_hashed_not_in_plain_text(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)
    stored = (await app_state["users"].find_one({"email": "jane@example.com"}))["password_reset"]
    assert code not in str(stored)
    assert stored["code_hash"] == password_reset.hash_code("jane@example.com", code)


async def test_asking_again_straight_away_does_not_send_another_code(client, app_state, whatsapps):
    await make_user(app_state)
    await ask_for_code(client, whatsapps)
    await ask_for_code(client, whatsapps)
    assert len(whatsapps) == 1


async def test_there_is_a_cap_on_codes_per_hour(client, app_state, whatsapps):
    user_id = await make_user(app_state)
    now = datetime.utcnow()
    # Three codes already sent in the last hour, the latest long enough ago to be past the cool-down.
    await app_state["users"].update_one(
        {"email": "jane@example.com"},
        {"$set": {"password_reset": {"code_hash": "x", "expires_at": now, "attempts": 0,
                                     "sent_at": [now - timedelta(minutes=50), now - timedelta(minutes=30), now - timedelta(minutes=5)]}}},
    )
    await ask_for_code(client, whatsapps)
    assert whatsapps == []

    # Once the oldest has aged out an hour ago, another is allowed.
    await app_state["users"].update_one(
        {"email": "jane@example.com"},
        {"$set": {"password_reset.sent_at": [now - timedelta(minutes=70), now - timedelta(minutes=30), now - timedelta(minutes=5)]}},
    )
    await ask_for_code(client, whatsapps)
    assert len(whatsapps) == 1


# ---------- booker: reset password ----------


async def reset(client, code, password=NEW, email="jane@example.com"):
    return await client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": password})


async def test_the_right_code_sets_a_new_password(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)

    assert (await reset(client, code)).status_code == 200
    assert (await login(client, NEW)).status_code == 200
    assert (await login(client, "old-password-1")).status_code == 401


async def test_a_code_only_works_once(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)
    assert (await reset(client, code)).status_code == 200
    again = await reset(client, code, password="another-new-password")
    assert again.status_code == 400
    assert (await login(client, NEW)).status_code == 200  # the first reset stands


async def test_a_wrong_code_is_refused_without_changing_anything(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)
    wrong = "000000" if code != "000000" else "111111"
    resp = await reset(client, wrong)
    assert resp.status_code == 400 and "wrong or has expired" in resp.json()["detail"]
    assert (await login(client, "old-password-1")).status_code == 200


async def test_five_wrong_guesses_lock_the_code_even_if_the_next_one_is_right(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(password_reset.MAX_ATTEMPTS):
        assert (await reset(client, wrong)).status_code == 400
    assert (await reset(client, code)).status_code == 400
    assert (await login(client, "old-password-1")).status_code == 200


async def test_an_expired_code_is_refused(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)
    await app_state["users"].update_one(
        {"email": "jane@example.com"}, {"$set": {"password_reset.expires_at": datetime.utcnow() - timedelta(seconds=1)}}
    )
    assert (await reset(client, code)).status_code == 400


async def test_a_code_for_one_account_does_not_work_on_another(client, app_state, whatsapps):
    await make_user(app_state)
    await make_user(app_state, email="other@example.com", phone="+27829999999")
    code = await ask_for_code(client, whatsapps)
    resp = await reset(client, code, email="other@example.com")
    assert resp.status_code == 400
    assert (await login(client, "old-password-1", email="other@example.com")).status_code == 200


async def test_a_reset_without_asking_first_is_refused(client, app_state, whatsapps):
    await make_user(app_state)
    assert (await reset(client, "123456")).status_code == 400
    assert (await reset(client, "123456", email="nobody@example.com")).status_code == 400


async def test_a_weak_password_or_malformed_code_is_rejected_outright(client, app_state, whatsapps):
    await make_user(app_state)
    code = await ask_for_code(client, whatsapps)
    assert (await reset(client, code, password="short")).status_code == 422
    assert (await reset(client, "12345")).status_code == 422
    assert (await reset(client, "abcdef")).status_code == 422
    assert (await reset(client, code, password="x" * 73)).status_code == 422
    assert (await reset(client, code)).status_code == 200  # the code survived those refusals


async def test_resetting_signs_out_sessions_opened_with_the_old_password(client, app_state, whatsapps, rooms_col):
    from tests.conftest import booking_payload, make_room

    user_id = await make_user(app_state)
    old_token = {"Authorization": f"Bearer {create_user_access_token(user_id)}"}
    room = await make_room(rooms_col)
    assert (await client.post("/api/bookings", json=booking_payload(room), headers=old_token)).status_code == 200

    code = await ask_for_code(client, whatsapps)
    await reset(client, code)

    # A token minted a moment before the reset is rejected from now on.
    import time

    time.sleep(1.1)  # tokens carry whole-second issue times
    assert (await client.post("/api/bookings", json=booking_payload(room, start_offset_days=6), headers=old_token)).status_code == 403
    fresh = (await login(client, NEW)).json()["access_token"]
    assert (
        await client.post("/api/bookings", json=booking_payload(room, start_offset_days=6), headers={"Authorization": f"Bearer {fresh}"})
    ).status_code == 200


# ---------- admin: change my password / reset another admin's ----------


async def test_an_admin_can_change_their_own_password(client, app_state):
    headers = await _make_admin(client)
    resp = await client.post(
        "/api/admin/change-password", json={"current_password": "secret123", "new_password": NEW}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()

    assert (await client.post("/api/admin/login", json={"email": "admin@example.com", "password": NEW})).status_code == 200
    assert (await client.post("/api/admin/login", json={"email": "admin@example.com", "password": "secret123"})).status_code == 401
    # The token returned works straight away, so the admin isn't thrown out by their own change.
    assert (await client.get("/api/admin/me", headers={"Authorization": f"Bearer {body['access_token']}"})).status_code == 200


async def test_the_old_admin_session_ends_when_the_password_changes(client, app_state):
    import time

    headers = await _make_admin(client)
    time.sleep(1.1)
    await client.post("/api/admin/change-password", json={"current_password": "secret123", "new_password": NEW}, headers=headers)
    assert (await client.get("/api/admin/me", headers=headers)).status_code == 401


async def test_changing_your_password_needs_the_current_one(client, app_state):
    headers = await _make_admin(client)
    resp = await client.post(
        "/api/admin/change-password", json={"current_password": "not-my-password", "new_password": NEW}, headers=headers
    )
    assert resp.status_code == 400
    assert (await client.post("/api/admin/login", json={"email": "admin@example.com", "password": "secret123"})).status_code == 200
    weak = await client.post("/api/admin/change-password", json={"current_password": "secret123", "new_password": "short"}, headers=headers)
    assert weak.status_code == 422


async def test_password_endpoints_need_an_admin_login(client, app_state):
    admin_id = str((await app_state["admins"].find_one({}) or {"_id": "64b000000000000000000000"})["_id"])
    assert (await client.post("/api/admin/change-password", json={"current_password": "x", "new_password": NEW})).status_code == 401
    assert (await client.get("/api/admin/admins")).status_code == 401
    assert (await client.post(f"/api/admin/admins/{admin_id}/password", json={"new_password": NEW})).status_code == 401


async def test_one_admin_can_reset_another_admins_password(client, app_state):
    headers = await _make_admin(client)
    second = await client.post(
        "/api/admin/register", json={"name": "Second Admin", "email": "second@example.com", "password": "second-pass-1"}, headers=headers
    )
    assert second.status_code == 200
    second_id = second.json()["id"]

    listed = (await client.get("/api/admin/admins", headers=headers)).json()
    assert {a["email"] for a in listed} == {"admin@example.com", "second@example.com"}
    assert all("password" not in a and "password_hash" not in a for a in listed)

    resp = await client.post(f"/api/admin/admins/{second_id}/password", json={"new_password": NEW}, headers=headers)
    assert resp.status_code == 200
    assert (await client.post("/api/admin/login", json={"email": "second@example.com", "password": NEW})).status_code == 200
    assert (await client.post("/api/admin/login", json={"email": "second@example.com", "password": "second-pass-1"})).status_code == 401

    assert (await client.post("/api/admin/admins/64b000000000000000000000/password", json={"new_password": NEW}, headers=headers)).status_code == 404
    assert (await client.post("/api/admin/admins/not-an-id/password", json={"new_password": NEW}, headers=headers)).status_code == 404
    assert (await client.post(f"/api/admin/admins/{second_id}/password", json={"new_password": "short"}, headers=headers)).status_code == 422


async def test_an_admin_setting_a_booker_password_signs_that_booker_out(client, app_state):
    import time

    admin = await _make_admin(client)
    user_id = await make_user(app_state)
    old = {"Authorization": f"Bearer {create_user_access_token(user_id)}"}
    time.sleep(1.1)
    resp = await client.patch(f"/api/admin/users/{user_id}", json={"password": "set-by-the-office"}, headers=admin)
    assert resp.status_code == 200
    assert (await login(client, "set-by-the-office")).status_code == 200
    from app.auth import _decode_user_token

    assert await _decode_user_token(old["Authorization"].split()[1]) is None
