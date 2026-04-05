"""Tests for /api/sessions routes: CRUD, graph update, messages."""

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


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/sessions",
        json={"idea": "Build a recommendation engine", "selected_model": "claude-sonnet-4-6"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["idea"] == "Build a recommendation engine"
    assert "id" in data
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_create_session_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/sessions",
        json={"idea": "Test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_sessions(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.get("/api/sessions", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 1
    ids = [s["id"] for s in data["items"]]
    assert test_session.id in ids


@pytest.mark.asyncio
async def test_list_sessions_pagination(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.get(
        "/api/sessions?page=1&limit=1", headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_get_session(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.get(
        f"/api/sessions/{test_session.id}", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == test_session.id
    assert data["idea"] == test_session.idea
    assert "messages" in data
    assert isinstance(data["messages"], list)


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient, auth_headers):
    resp = await client.get(
        "/api/sessions/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session_includes_messages(
    client: AsyncClient,
    auth_headers,
    test_session,
    db: AsyncSession,
):
    """Regression: GET /sessions/{id} must return persisted messages."""
    from app.db.models.message import Message

    msg = Message(
        session_id=test_session.id,
        role="user",
        content="Hello world",
        message_index=0,
    )
    db.add(msg)
    await db.flush()

    resp = await client.get(
        f"/api/sessions/{test_session.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello world"
    assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_update_session_name(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.patch(
        f"/api/sessions/{test_session.id}",
        json={"name": "Renamed Session"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Renamed Session"


@pytest.mark.asyncio
async def test_update_session_invalid_model(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.patch(
        f"/api/sessions/{test_session.id}",
        json={"selected_model": "gpt-4o"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_session(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.delete(
        f"/api/sessions/{test_session.id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Confirm it's gone
    get_resp = await client.get(
        f"/api/sessions/{test_session.id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_update_graph(
    client: AsyncClient, auth_headers, test_session
):
    resp = await client.put(
        f"/api/sessions/{test_session.id}/graph",
        json={"graph_state": VALID_GRAPH},
        headers=auth_headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_update_session_not_found(client: AsyncClient, auth_headers):
    resp = await client.patch(
        "/api/sessions/00000000-0000-0000-0000-000000000000",
        json={"name": "x"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_session_forbidden(
    client: AsyncClient, test_session, db: AsyncSession
):
    from app.db.models.user import User
    from app.services.auth_service import create_access_token, hash_password

    other = User(email="upd-other@example.com", name="O", password_hash=hash_password("p"))
    db.add(other)
    await db.flush()
    resp = await client.patch(
        f"/api/sessions/{test_session.id}",
        json={"name": "x"},
        headers={"Authorization": f"Bearer {create_access_token(other.id)}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_session_valid_model(
    client: AsyncClient, auth_headers, test_session
):
    """PATCH with a valid model name should succeed and persist the change."""
    resp = await client.patch(
        f"/api/sessions/{test_session.id}",
        json={"selected_model": "claude-haiku-4-5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["selected_model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_delete_session_not_found(client: AsyncClient, auth_headers):
    resp = await client.delete(
        "/api/sessions/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_forbidden(
    client: AsyncClient, test_session, db: AsyncSession
):
    from app.db.models.user import User
    from app.services.auth_service import create_access_token, hash_password

    other = User(email="del-other@example.com", name="O", password_hash=hash_password("p"))
    db.add(other)
    await db.flush()
    resp = await client.delete(
        f"/api/sessions/{test_session.id}",
        headers={"Authorization": f"Bearer {create_access_token(other.id)}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_graph_not_found(client: AsyncClient, auth_headers):
    resp = await client.put(
        "/api/sessions/00000000-0000-0000-0000-000000000000/graph",
        json={"graph_state": VALID_GRAPH},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_graph_forbidden(
    client: AsyncClient, test_session, db: AsyncSession
):
    from app.db.models.user import User
    from app.services.auth_service import create_access_token, hash_password

    other = User(email="graph-other@example.com", name="O", password_hash=hash_password("p"))
    db.add(other)
    await db.flush()
    resp = await client.put(
        f"/api/sessions/{test_session.id}/graph",
        json={"graph_state": VALID_GRAPH},
        headers={"Authorization": f"Bearer {create_access_token(other.id)}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_session_forbidden_for_other_user(
    client: AsyncClient,
    auth_headers,
    test_session,
    db: AsyncSession,
):
    """A different user must not access another user's session."""
    from app.db.models.user import User
    from app.services.auth_service import create_access_token, hash_password

    other = User(
        email="other@example.com",
        name="Other",
        password_hash=hash_password("pass"),
    )
    db.add(other)
    await db.flush()

    other_token = create_access_token(other.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = await client.get(
        f"/api/sessions/{test_session.id}", headers=other_headers
    )
    assert resp.status_code == 403
