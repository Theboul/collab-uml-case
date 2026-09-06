from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app


@pytest.fixture(autouse=True)
def run_init_db():
    import asyncio

    from backend_case.app.shared.db.base import Base, engine, init_db

    async def _setup():
        await init_db()
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

    asyncio.run(_setup())

@pytest.fixture
def client():
    return TestClient(app)

def test_register_and_login_flow(client):
    # 1. Register
    reg_payload = {
        "email": "designer@schemacraft.dev",
        "password": "Password123!",
        "fullName": "Schema Designer"
    }
    res = client.post("/api/v2/auth/register", json=reg_payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert "accessToken" in data
    assert data["tokenType"] == "Bearer"
    assert data["user"]["email"] == "designer@schemacraft.dev"
    assert data["user"]["fullName"] == "Schema Designer"
    assert "sc_refresh_token" in res.cookies

    # 2. Duplicate registration returns 409
    dup_res = client.post("/api/v2/auth/register", json=reg_payload)
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "AUTH_EMAIL_ALREADY_EXISTS"

    # 3. Login with password
    login_payload = {
        "email": "designer@schemacraft.dev",
        "password": "Password123!"
    }
    login_res = client.post("/api/v2/auth/login", json=login_payload)
    assert login_res.status_code == 200
    login_data = login_res.json()
    access_token = login_data["accessToken"]
    assert access_token

    # 4. Access protected profile
    me_res = client.get(
        "/api/v2/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "designer@schemacraft.dev"
    assert "password" in me_data["identities"]

    # 5. Refresh token rotation
    refresh_res = client.post("/api/v2/auth/refresh")
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["accessToken"]
    assert new_access_token != access_token

    # 6. Logout server-side revocation
    logout_res = client.post("/api/v2/auth/logout")
    assert logout_res.status_code == 204

    # Refresh again should fail since session was revoked
    fail_refresh = client.post("/api/v2/auth/refresh")
    assert fail_refresh.status_code == 401
    assert fail_refresh.json()["code"] == "AUTH_SESSION_EXPIRED"

def test_login_invalid_credentials(client):
    res = client.post("/api/v2/auth/login", json={
        "email": "nonexistent@schemacraft.dev",
        "password": "WrongPassword!"
    })
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_INVALID_CREDENTIALS"

def test_google_auth_and_account_linking(client):
    # Register password account first
    client.post("/api/v2/auth/register", json={
        "email": "alex@googleuser.com",
        "password": "Password123!",
        "fullName": "Alex Original"
    })

    # Mock google tokeninfo response
    mock_google_info = {
        "sub": "google-sub-12345678",
        "email": "alex@googleuser.com",
        "email_verified": "true",
        "name": "Alex Google",
        "picture": "https://lh3.googleusercontent.com/a/photo.jpg"
    }

    with patch("backend_case.app.shared.security.service.verify_google_token", return_value=mock_google_info):
        res = client.post("/api/v2/auth/google", json={"id_token": "valid-mocked-token"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["user"]["email"] == "alex@googleuser.com"
        access_token = data["accessToken"]

        # Check me profile has both providers linked
        me_res = client.get(
            "/api/v2/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_res.status_code == 200
        identities = me_res.json()["identities"]
        assert "password" in identities
        assert "google" in identities


def test_get_public_auth_config(client):
    res = client.get("/api/v2/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert "googleClientId" in data
