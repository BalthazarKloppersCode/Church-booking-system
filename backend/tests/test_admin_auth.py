from app.config import settings


async def test_first_admin_requires_correct_setup_secret(client):
    missing_secret = await client.post(
        "/api/admin/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "hunter22"},
    )
    assert missing_secret.status_code == 403

    wrong_secret = await client.post(
        "/api/admin/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "hunter22",
            "setup_secret": "not-the-secret",
        },
    )
    assert wrong_secret.status_code == 403

    correct_secret = await client.post(
        "/api/admin/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "hunter22",
            "setup_secret": settings.admin_setup_secret,
        },
    )
    assert correct_secret.status_code == 200
    assert correct_secret.json()["email"] == "alice@example.com"


async def test_registration_disabled_when_no_setup_secret_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_setup_secret", "")
    resp = await client.post(
        "/api/admin/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "hunter22"},
    )
    assert resp.status_code == 503


async def test_second_admin_requires_existing_admin_login(client):
    await client.post(
        "/api/admin/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "hunter22",
            "setup_secret": settings.admin_setup_secret,
        },
    )

    no_auth = await client.post(
        "/api/admin/register",
        json={"name": "Bob", "email": "bob@example.com", "password": "hunter22"},
    )
    assert no_auth.status_code == 401

    login = await client.post(
        "/api/admin/login", json={"email": "alice@example.com", "password": "hunter22"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    with_auth = await client.post(
        "/api/admin/register",
        json={"name": "Bob", "email": "bob@example.com", "password": "hunter22"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert with_auth.status_code == 200
    assert with_auth.json()["email"] == "bob@example.com"


async def test_login_wrong_password_rejected(client):
    await client.post(
        "/api/admin/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "hunter22",
            "setup_secret": settings.admin_setup_secret,
        },
    )
    resp = await client.post(
        "/api/admin/login", json={"email": "alice@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_me_requires_valid_token(client):
    no_token = await client.get("/api/admin/me")
    assert no_token.status_code == 401

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
    token = login.json()["access_token"]

    resp = await client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"
