"""Tests for /api/users routes: profile, password, API key, delete."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers, test_user):
    resp = await client.get("/api/users/me", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == test_user.email
    assert data["name"] == test_user.name
    assert data["has_api_key"] is False


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth_headers):
    resp = await client.patch(
        "/api/users/me",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_change_password_success(
    client: AsyncClient, auth_headers, test_user
):
    from tests.conftest import TEST_USER_PASSWORD

    resp = await client.post(
        "/api/users/me/password",
        json={
            "current_password": TEST_USER_PASSWORD,
            "new_password": "NewSecurePass456!",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    client: AsyncClient, auth_headers
):
    resp = await client.post(
        "/api/users/me/password",
        json={
            "current_password": "wrongpassword",
            "new_password": "NewSecurePass456!",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_api_key_when_none(client: AsyncClient, auth_headers):
    # Deleting a non-existent key should still succeed (idempotent)
    resp = await client.delete("/api/users/me/api-key", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["has_api_key"] is False


@pytest.mark.asyncio
async def test_delete_account_success(
    client: AsyncClient, auth_headers, test_user
):
    import json as _json

    from tests.conftest import TEST_USER_PASSWORD

    resp = await client.request(
        "DELETE",
        "/api/users/me",
        content=_json.dumps({"password": TEST_USER_PASSWORD}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_account_wrong_password(
    client: AsyncClient, auth_headers
):
    import json as _json

    resp = await client.request(
        "DELETE",
        "/api/users/me",
        content=_json.dumps({"password": "wrongpassword"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# API key validation (schema validator — sk-ant- prefix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_api_key_invalid_prefix_rejected(
    client: AsyncClient, auth_headers
):
    """Keys not starting with 'sk-ant-' are rejected before hitting Anthropic."""
    resp = await client.post(
        "/api/users/me/api-key",
        json={"api_key": "sk-openai-not-anthropic"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_api_key_invalid_anthropic_key(
    client: AsyncClient, auth_headers, mocker
):
    """Valid format but Anthropic rejects it → 422."""
    import anthropic

    mock_client = mocker.AsyncMock()
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {}
    mock_resp.json.return_value = {}
    mock_client.models.list.side_effect = anthropic.AuthenticationError(
        "bad key", response=mock_resp, body={}
    )
    mocker.patch("anthropic.AsyncAnthropic", return_value=mock_client)

    resp = await client.post(
        "/api/users/me/api-key",
        json={"api_key": "sk-ant-fake-but-valid-format"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "Invalid Anthropic API key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_api_key_network_error(
    client: AsyncClient, auth_headers, mocker
):
    """Any other error from Anthropic validation → 422 with generic message."""
    import anthropic

    mock_client = mocker.AsyncMock()
    mock_client.models.list.side_effect = Exception("network error")
    mocker.patch("anthropic.AsyncAnthropic", return_value=mock_client)

    resp = await client.post(
        "/api/users/me/api-key",
        json={"api_key": "sk-ant-fake-key-abc"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "Could not validate" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_api_key_success(
    client: AsyncClient, auth_headers, mocker
):
    """Valid key accepted by Anthropic → stored encrypted, has_api_key=True."""
    import anthropic

    mock_client = mocker.AsyncMock()
    mock_client.models.list.return_value = []
    mocker.patch("anthropic.AsyncAnthropic", return_value=mock_client)

    resp = await client.post(
        "/api/users/me/api-key",
        json={"api_key": "sk-ant-valid-key-xyz"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["has_api_key"] is True


# ---------------------------------------------------------------------------
# get_db — exercise the real session factory path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_db_commits_and_yields_session(mocker):
    """Verify get_db yields a working AsyncSession and commits on success."""
    from app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    # Patch AsyncSessionLocal to return a real session against the test DB
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    test_engine = create_async_engine(
        "postgresql+asyncpg://idealens:idealens@localhost:5432/idealens_test",
        poolclass=NullPool,
    )
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    mocker.patch("app.db.session.AsyncSessionLocal", TestSession)

    gen = get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)

    # Drive generator to completion (simulates successful request)
    try:
        await gen.asend(None)
    except StopAsyncIteration:
        pass

    await test_engine.dispose()
