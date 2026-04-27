"""Tests for /api/chat endpoint and related SSE paths."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


VALID_GRAPH = {
    "nodes": [
        {
            "id": "root",
            "type": "root",
            "label": "My idea",
            "content": "My idea content",
            "score": None,
            "parent_id": None,
            "position": {"x": 400, "y": 300},
            "userPositioned": False,
        }
    ],
    "edges": [],
}

_CHAT_BODY = {
    "message": "Analyse this idea",
    "graph_state": VALID_GRAPH,
    "model": "claude-sonnet-4-6",
}


# ---------------------------------------------------------------------------
# Auth / validation guards (no Anthropic key needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient, test_session):
    resp = await client.post(
        "/api/chat",
        json={"session_id": test_session.id, **_CHAT_BODY},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_invalid_model(client: AsyncClient, auth_headers, test_session):
    resp = await client.post(
        "/api/chat",
        json={
            "session_id": test_session.id,
            "message": "hi",
            "graph_state": VALID_GRAPH,
            "model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# SSE error paths (no API key set on the user)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_no_api_key_returns_sse_error(
    client: AsyncClient, auth_headers, test_session
):
    """User has no encrypted_api_key → SSE error event, not 4xx."""
    resp = await client.post(
        "/api/chat",
        json={"session_id": test_session.id, **_CHAT_BODY},
        headers=auth_headers,
    )
    # The endpoint returns a StreamingResponse even on soft errors
    assert resp.status_code == 200
    assert "event: error" in resp.text


@pytest.mark.asyncio
async def test_chat_session_not_found_returns_sse_error(
    client: AsyncClient, auth_headers
):
    """Non-existent session → SSE error, not 404."""
    resp = await client.post(
        "/api/chat",
        json={
            "session_id": "00000000-0000-0000-0000-000000000000",
            **_CHAT_BODY,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "event: error" in resp.text


@pytest.mark.asyncio
async def test_chat_other_users_session_returns_sse_error(
    client: AsyncClient,
    test_session,
    db: AsyncSession,
):
    """Accessing another user's session via chat → SSE error."""
    from app.db.models.user import User
    from app.services.auth_service import create_access_token, hash_password

    other = User(
        email="other2@example.com",
        name="Other",
        password_hash=hash_password("pw"),
    )
    db.add(other)
    await db.flush()

    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}
    resp = await client.post(
        "/api/chat",
        json={"session_id": test_session.id, **_CHAT_BODY},
        headers=other_headers,
    )
    assert resp.status_code == 200
    assert "event: error" in resp.text


# ---------------------------------------------------------------------------
# SSE reconnection replay (_replay_completed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_reconnect_replay(
    client: AsyncClient,
    auth_headers,
    test_user,
    test_session,
    db: AsyncSession,
):
    """If Last-Event-ID matches a completed assistant message, replay its graph actions."""
    from app.db.models.message import Message
    from app.services.encryption_service import encrypt_api_key

    # Give the user a dummy encrypted key so the API-key check passes
    test_user.encrypted_api_key = encrypt_api_key("sk-ant-replay-test-key")
    db.add(test_user)
    await db.flush()

    graph_actions = [
        {
            "action": "add",
            "payload": {
                "id": "c1",
                "type": "concept",
                "label": "L",
                "content": "C",
                "score": None,
                "parent_id": None,
            },
        }
    ]
    msg = Message(
        id="replay-uuid",
        session_id=test_session.id,
        role="assistant",
        content="hello",
        message_index=1,
        metadata_={"graph_actions": graph_actions},
    )
    db.add(msg)
    await db.flush()

    resp = await client.post(
        "/api/chat",
        json={"session_id": test_session.id, **_CHAT_BODY},
        headers={**auth_headers, "last-event-id": "replay-uuid"},
    )
    assert resp.status_code == 200
    assert "graph_action" in resp.text
    assert "event: done" in resp.text


# ---------------------------------------------------------------------------
# Full SSE stream (mocked LLM) — covers _stream + connect action branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_full_sse_stream_with_mock(
    client: AsyncClient,
    auth_headers,
    test_user,
    test_session,
    db: AsyncSession,
    mocker,
):
    """Happy path: user has API key + mocked LLM → SSE tokens + graph_action + done."""
    import json as _json
    from app.services.encryption_service import encrypt_api_key
    from app.schemas.graph import (
        AddNodeAction,
        ConnectAction,
        ConnectPayload,
        DimensionType,
        LLMResponse,
        NodePayload,
    )

    # Give user an encrypted key
    test_user.encrypted_api_key = encrypt_api_key("sk-ant-stream-test")
    db.add(test_user)
    await db.flush()

    # Build a fake parsed response with an add + connect action
    add_action = AddNodeAction(
        action="add",
        payload=NodePayload(
            id="c1",
            type=DimensionType.CONCEPT,
            label="L",
            content="C",
            score=None,
            parent_id=None,
        ),
    )
    connect_action = ConnectAction(
        action="connect",
        payload=ConnectPayload(source="root", target="c1"),
    )
    fake_response = LLMResponse(
        message="Great idea!", graph_actions=[add_action, connect_action]
    )

    async def fake_stream(*args, **kwargs):
        yield "token", "Great "
        yield "token", "idea!"
        yield "parsed", fake_response
        yield "done", None

    mocker.patch(
        "app.api.routes.chat.llm_service.stream_with_heartbeat",
        side_effect=fake_stream,
    )

    resp = await client.post(
        "/api/chat",
        json={"session_id": test_session.id, **_CHAT_BODY},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    text = resp.text
    assert "event: token" in text
    assert "event: graph_action" in text
    assert "event: done" in text
    # Both add and connect actions should appear
    assert '"action": "add"' in text
    assert '"action": "connect"' in text


@pytest.mark.asyncio
async def test_chat_context_summarization(
    client: AsyncClient,
    auth_headers,
    test_user,
    test_session,
    db: AsyncSession,
    mocker,
):
    """When messages exceed CONTEXT_WINDOW_MAX_MESSAGES, summarize_messages is called."""
    from app.core.config import get_settings
    from app.db.models.message import Message
    from app.services.encryption_service import encrypt_api_key
    from app.schemas.graph import LLMResponse

    test_user.encrypted_api_key = encrypt_api_key("sk-ant-ctx-test")
    db.add(test_user)
    await db.flush()

    # Insert more messages than the context window allows
    limit = get_settings().CONTEXT_WINDOW_MAX_MESSAGES
    for i in range(limit + 2):
        db.add(
            Message(
                session_id=test_session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"msg {i}",
                message_index=i,
            )
        )
    await db.flush()

    summarize_mock = mocker.patch(
        "app.api.routes.chat.llm_service.summarize_messages",
        new_callable=mocker.AsyncMock,
        return_value="A concise summary.",
    )

    async def fake_stream(*args, **kwargs):
        yield "token", "ok"
        yield "parsed", LLMResponse(message="ok", graph_actions=[])
        yield "done", None

    mocker.patch(
        "app.api.routes.chat.llm_service.stream_with_heartbeat",
        side_effect=fake_stream,
    )

    resp = await client.post(
        "/api/chat",
        json={"session_id": test_session.id, **_CHAT_BODY},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert summarize_mock.called


# ---------------------------------------------------------------------------
# Models list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_models_list(client: AsyncClient):
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert all("id" in m for m in data)


# ---------------------------------------------------------------------------
# Dependency: get_current_user error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_bearer_token_returns_401(client: AsyncClient):
    resp = await client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_for_deleted_user_returns_401(
    client: AsyncClient,
    db: AsyncSession,
):
    """A valid token whose user no longer exists → 401."""
    from app.services.auth_service import create_access_token

    # Generate a token for a user ID that doesn't exist in the DB
    ghost_token = create_access_token("ghost-user-id-that-does-not-exist")
    resp = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Main app — security headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_hsts_header_only_in_production(mocker, client: AsyncClient):
    """HSTS header must NOT appear in development environment."""
    resp = await client.get("/health")
    assert "strict-transport-security" not in resp.headers


@pytest.mark.asyncio
async def test_hsts_header_in_production(mocker):
    """HSTS header must appear when ENVIRONMENT=production."""
    from app.core.config import Settings, get_settings
    from app.main import create_app
    from httpx import AsyncClient, ASGITransport

    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="test-secret-long-enough-for-testing-purposes-1234",
        API_KEY_ENCRYPTION_KEY="JCsDK3PQ6Dt8GmniYwbCm2uWHc8aU8xKmaC8oY3njrE=",
    )
    mocker.patch("app.main.get_settings", return_value=prod_settings)
    mocker.patch("app.core.config.get_settings", return_value=prod_settings)

    _app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/health")
    assert "strict-transport-security" in resp.headers
