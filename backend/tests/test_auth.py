"""Tests for /auth routes: register, login, refresh, logout."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "name": "New User",
            "password": "SecurePass123!",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert resp.cookies.get("refresh_token") is not None


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    resp = await client.post(
        "/auth/register",
        json={
            "email": test_user.email,
            "name": "Dup",
            "password": "SecurePass123!",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    from tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD

    resp = await client.post(
        "/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()
    assert resp.cookies.get("refresh_token") is not None


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    from tests.conftest import TEST_USER_EMAIL

    resp = await client.post(
        "/auth/login",
        json={"email": TEST_USER_EMAIL, "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "pass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, test_user):
    from tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD

    # Login to get the refresh cookie
    login = await client.post(
        "/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert login.status_code == 200

    # Use the refresh endpoint
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_without_cookie(client: AsyncClient):
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_jwt_cookie(client: AsyncClient):
    """Malformed JWT in the refresh cookie → 401 (JWTError branch)."""
    client.cookies.set("refresh_token", "not.a.valid.jwt", path="/auth")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_expired_stored_token(
    client: AsyncClient, test_user, db
):
    """Valid JWT but the stored token is expired → 401."""
    from datetime import datetime, timedelta, timezone
    from app.db.models.refresh_token import RefreshToken
    from app.services.auth_service import create_refresh_token

    # Create a token that is expired in the DB (expires_at in the past)
    token_str = create_refresh_token(test_user.id)
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    db.add(RefreshToken(token=token_str, user_id=test_user.id, expires_at=past))
    await db.flush()

    client.cookies.set("refresh_token", token_str, path="/auth")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, test_user):
    from tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD

    await client.post(
        "/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )

    resp = await client.post("/auth/logout")
    assert resp.status_code == 204
