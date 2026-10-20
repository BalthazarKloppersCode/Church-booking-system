from tests.test_calendar_sync import _make_admin

NEW = "joshgenpinehurst@gmail.com"


async def test_an_admin_can_change_the_email_they_log_in_with(client):
    headers = await _make_admin(client)  # admin@example.com / secret123
    resp = await client.post("/api/admin/change-email", json={"current_password": "secret123", "new_email": NEW}, headers=headers)
    assert resp.status_code == 200 and resp.json()["email"] == NEW

    assert (await client.post("/api/admin/login", json={"email": NEW, "password": "secret123"})).status_code == 200
    assert (await client.post("/api/admin/login", json={"email": "admin@example.com", "password": "secret123"})).status_code == 401
    # The session they were in keeps working, and shows the new email.
    me = await client.get("/api/admin/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == NEW


async def test_the_current_password_is_required(client):
    headers = await _make_admin(client)
    resp = await client.post("/api/admin/change-email", json={"current_password": "wrong-password", "new_email": NEW}, headers=headers)
    assert resp.status_code == 400 and "current password" in resp.json()["detail"]
    assert (await client.post("/api/admin/login", json={"email": "admin@example.com", "password": "secret123"})).status_code == 200


async def test_it_cannot_take_another_admins_email_in_any_case(client):
    headers = await _make_admin(client)
    second = await client.post(
        "/api/admin/register", json={"name": "Second", "email": "Second@Example.com", "password": "second-pass-1"}, headers=headers
    )
    assert second.status_code == 200
    for taken in ("second@example.com", "SECOND@example.com"):
        resp = await client.post("/api/admin/change-email", json={"current_password": "secret123", "new_email": taken}, headers=headers)
        assert resp.status_code == 400 and "already uses" in resp.json()["detail"]


async def test_keeping_the_same_email_is_allowed_and_a_bad_one_is_refused(client):
    headers = await _make_admin(client)
    same = await client.post("/api/admin/change-email", json={"current_password": "secret123", "new_email": "admin@example.com"}, headers=headers)
    assert same.status_code == 200
    bad = await client.post("/api/admin/change-email", json={"current_password": "secret123", "new_email": "not-an-email"}, headers=headers)
    assert bad.status_code == 422


async def test_it_needs_an_admin_login(client):
    resp = await client.post("/api/admin/change-email", json={"current_password": "x", "new_email": NEW})
    assert resp.status_code == 401
