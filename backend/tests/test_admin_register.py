from tests.test_calendar_sync import _make_admin


async def add(client, headers, **overrides):
    body = {"name": "Josh Church", "email": "joshgenpinehurst@gmail.com", "password": "starting-pass-1"}
    body.update(overrides)
    return await client.post("/api/admin/register", json=body, headers=headers)


async def test_a_logged_in_admin_can_add_another_admin_who_can_log_in(client):
    headers = await _make_admin(client)
    resp = await add(client, headers)
    assert resp.status_code == 200 and resp.json()["email"] == "joshgenpinehurst@gmail.com"

    login = await client.post("/api/admin/login", json={"email": "joshgenpinehurst@gmail.com", "password": "starting-pass-1"})
    assert login.status_code == 200
    token = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/admin/me", headers=token)).status_code == 200
    assert (await client.get("/api/admin/dashboard", headers=token)).status_code == 200  # full access
    listed = (await client.get("/api/admin/admins", headers=headers)).json()
    assert {a["email"] for a in listed} == {"admin@example.com", "joshgenpinehurst@gmail.com"}


async def test_the_new_admins_email_cannot_match_an_existing_one_in_any_case(client):
    headers = await _make_admin(client)
    for same in ("admin@example.com", "ADMIN@example.com", "Admin@Example.com"):
        resp = await add(client, headers, email=same)
        assert resp.status_code == 400 and "already exists" in resp.json()["detail"], same


async def test_a_weak_password_or_blank_name_is_refused(client):
    headers = await _make_admin(client)
    assert (await add(client, headers, password="short")).status_code == 422
    assert (await add(client, headers, password="x" * 73)).status_code == 422
    assert (await add(client, headers, name="")).status_code == 422
    assert (await add(client, headers, email="not-an-email")).status_code == 422


async def test_nobody_can_add_an_admin_without_being_one(client, booker_headers):
    await _make_admin(client)
    assert (await add(client, {})).status_code == 401
    assert (await add(client, booker_headers)).status_code == 401  # a booker is not an admin
