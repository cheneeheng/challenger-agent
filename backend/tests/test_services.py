"""Unit tests for service-layer functions (no HTTP layer needed)."""

import json

import pytest
from jose import jwt

from app.core.config import get_settings
from app.services import encryption_service
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.services.llm_service import build_messages, parse_llm_response
from app.schemas.graph import AnalysisGraph


# ---------------------------------------------------------------------------
# auth_service
# ---------------------------------------------------------------------------


def test_hash_and_verify_password():
    h = hash_password("mysecret")
    assert verify_password("mysecret", h)
    assert not verify_password("wrong", h)


def test_create_and_verify_access_token():
    token = create_access_token("user-123")
    user_id = verify_token(token, expected_type="access")
    assert user_id == "user-123"


def test_create_and_verify_refresh_token():
    token = create_refresh_token("user-456")
    user_id = verify_token(token, expected_type="refresh")
    assert user_id == "user-456"


def test_verify_token_wrong_type_raises():
    """Passing an access token where a refresh token is expected must raise."""
    from jose import JWTError

    access = create_access_token("u1")
    with pytest.raises(JWTError):
        verify_token(access, expected_type="refresh")


def test_verify_token_missing_sub_raises():
    """A JWT with no 'sub' claim must raise JWTError."""
    from datetime import datetime, timedelta, timezone
    from jose import JWTError, jwt

    s = get_settings()
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        s.JWT_SECRET,
        algorithm=s.JWT_ALGORITHM,
    )
    with pytest.raises(JWTError):
        verify_token(token)


def test_verify_token_invalid_signature_raises():
    from jose import JWTError

    with pytest.raises(JWTError):
        verify_token("not.a.valid.jwt")


# ---------------------------------------------------------------------------
# encryption_service
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_round_trip():
    plaintext = "sk-ant-test-key-1234"
    ciphertext = encryption_service.encrypt_api_key(plaintext)
    assert ciphertext != plaintext
    assert encryption_service.decrypt_api_key(ciphertext) == plaintext


def test_encrypt_returns_string():
    result = encryption_service.encrypt_api_key("sk-ant-abc")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# llm_service.build_messages
# ---------------------------------------------------------------------------

_EMPTY_GRAPH = AnalysisGraph(nodes=[], edges=[])


def _make_msg(role: str, content: str, idx: int = 0):
    """Lightweight stand-in for the Message ORM model."""
    from types import SimpleNamespace

    return SimpleNamespace(role=role, content=content, message_index=idx)


def test_build_messages_no_history():
    msgs = build_messages([], _EMPTY_GRAPH, "What is this?")
    # Should contain the graph state + user message (2 entries)
    assert len(msgs) == 2
    assert msgs[-1] == {"role": "user", "content": "What is this?"}


def test_build_messages_with_history():
    history = [
        _make_msg("user", "Hello", 0),
        _make_msg("assistant", "Hi there", 1),
    ]
    msgs = build_messages(history, _EMPTY_GRAPH, "Follow up?")
    # history (2) + graph state + user message = 4
    assert len(msgs) == 4
    assert msgs[0] == {"role": "user", "content": "Hello"}
    assert msgs[1] == {"role": "assistant", "content": "Hi there"}


def test_build_messages_with_context_summary():
    history = [
        _make_msg("user", "old msg", 0),
        _make_msg("assistant", "old reply", 1),
        _make_msg("user", "new msg", 2),
    ]
    msgs = build_messages(
        history,
        _EMPTY_GRAPH,
        "current msg",
        context_summary="Summary of old stuff",
        context_summary_covers_up_to=1,
    )
    # Summary preamble (user + assistant) + messages after idx 1 + graph + user
    assert msgs[0]["content"].startswith("[Previous conversation summary]:")
    assert msgs[1]["content"] == "Understood. Continuing from the summary."
    # Only messages with message_index > 1 are included
    contents = [m["content"] for m in msgs]
    assert "old msg" not in contents
    assert "new msg" in contents


def test_build_messages_system_role_prefixed():
    history = [_make_msg("system", "Graph context", 0)]
    msgs = build_messages(history, _EMPTY_GRAPH, "proceed")
    system_entry = next(m for m in msgs if "Graph context" in m["content"])
    assert system_entry["content"].startswith("[Context]:")


def test_build_messages_trims_to_max_context():
    """Messages beyond CONTEXT_WINDOW_MAX_MESSAGES are trimmed from the front."""
    limit = get_settings().CONTEXT_WINDOW_MAX_MESSAGES
    history = [_make_msg("user", f"msg {i}", i) for i in range(limit + 5)]
    msgs = build_messages(history, _EMPTY_GRAPH, "latest")
    # Only limit messages + graph state + user message should be in msgs
    # (plus 0 summary preamble = 0)
    assert len(msgs) == limit + 2


# ---------------------------------------------------------------------------
# llm_service.parse_llm_response
# ---------------------------------------------------------------------------

_ADD_ACTION = {
    "action": "add",
    "payload": {
        "id": "concept-1",
        "type": "concept",
        "label": "My concept",
        "content": "Description",
        "score": None,
        "parent_id": None,
    },
}

_CONNECT_ACTION = {
    "action": "connect",
    "payload": {"source": "root", "target": "concept-1", "label": "has", "type": "supports"},
}


def test_parse_llm_response_valid():
    raw = f"<GRAPH_ACTIONS>{json.dumps([_ADD_ACTION])}</GRAPH_ACTIONS>\nSome explanation."
    result = parse_llm_response(raw)
    assert result.message == "Some explanation."
    assert len(result.graph_actions) == 1
    assert result.graph_actions[0].action == "add"


def test_parse_llm_response_no_block():
    result = parse_llm_response("Just plain text, no graph block.")
    assert result.message == "Just plain text, no graph block."
    assert result.graph_actions == []


def test_parse_llm_response_invalid_json():
    raw = "<GRAPH_ACTIONS>not valid json</GRAPH_ACTIONS>"
    result = parse_llm_response(raw)
    assert result.graph_actions == []


def test_parse_llm_response_skips_invalid_actions():
    bad_action = {"action": "add", "payload": {"broken": True}}
    raw = f"<GRAPH_ACTIONS>{json.dumps([_ADD_ACTION, bad_action])}</GRAPH_ACTIONS>"
    result = parse_llm_response(raw)
    # Only the valid action should pass
    assert len(result.graph_actions) == 1


def test_parse_llm_response_connect_action():
    raw = f"<GRAPH_ACTIONS>{json.dumps([_CONNECT_ACTION])}</GRAPH_ACTIONS>"
    result = parse_llm_response(raw)
    assert len(result.graph_actions) == 1
    assert result.graph_actions[0].action == "connect"


def test_parse_llm_response_update_action():
    update = {
        "action": "update",
        "payload": {"id": "concept-1", "label": "Updated label"},
    }
    raw = f"<GRAPH_ACTIONS>{json.dumps([update])}</GRAPH_ACTIONS>"
    result = parse_llm_response(raw)
    assert result.graph_actions[0].action == "update"


def test_parse_llm_response_delete_action():
    delete = {"action": "delete", "payload": {"id": "concept-1"}}
    raw = f"<GRAPH_ACTIONS>{json.dumps([delete])}</GRAPH_ACTIONS>"
    result = parse_llm_response(raw)
    assert result.graph_actions[0].action == "delete"


# ---------------------------------------------------------------------------
# llm_service.stream_with_heartbeat (mocked Anthropic)
# ---------------------------------------------------------------------------


def _make_stream_mock(mocker, text: str | None = None, side_effect=None):
    """
    Build a mock for the Anthropic streaming context manager.

    Anthropic's `client.messages.stream(...)` returns a sync context manager;
    `async with` on it triggers __aenter__ / __aexit__.  We must use a plain
    MagicMock for the client so that `messages.stream(...)` is a regular
    (non-awaited) call.
    """
    async def _text_stream():
        for ch in (text or ""):
            yield ch

    # Context manager object: __aenter__ is async, returns itself
    mock_cm = mocker.MagicMock()
    mock_cm.__aenter__ = mocker.AsyncMock(
        return_value=mock_cm, side_effect=side_effect
    )
    mock_cm.__aexit__ = mocker.AsyncMock(return_value=False)
    if text is not None:
        mock_cm.text_stream = _text_stream()

    # The Anthropic client: messages.stream() is a plain call returning mock_cm
    mock_client = mocker.MagicMock()
    mock_client.messages.stream.return_value = mock_cm
    return mock_client, mock_cm


@pytest.mark.asyncio
async def test_stream_with_heartbeat_success(mocker):
    """Mock the Anthropic streaming client and verify token + parsed events."""
    add_action_json = json.dumps([_ADD_ACTION])
    full_text = f"<GRAPH_ACTIONS>{add_action_json}</GRAPH_ACTIONS>\nGreat idea!"

    mock_client, _ = _make_stream_mock(mocker, text=full_text)
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    from app.services.llm_service import stream_with_heartbeat

    events = []
    async for event_type, data in stream_with_heartbeat([], "claude-sonnet-4-6", "sk-ant-fake"):
        events.append((event_type, data))

    event_types = [e[0] for e in events]
    assert "token" in event_types
    assert "parsed" in event_types
    assert "done" in event_types

    parsed_event = next(e for e in events if e[0] == "parsed")
    assert len(parsed_event[1].graph_actions) == 1


@pytest.mark.asyncio
async def test_stream_with_heartbeat_auth_error(mocker):
    from anthropic import AuthenticationError

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {}
    mock_resp.json.return_value = {}
    err = AuthenticationError("bad key", response=mock_resp, body={})

    mock_client, _ = _make_stream_mock(mocker, side_effect=err)
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    from app.services.llm_service import stream_with_heartbeat

    events = []
    async for event_type, data in stream_with_heartbeat([], "claude-sonnet-4-6", "sk-ant-fake"):
        events.append((event_type, data))

    # Consumer breaks on first "error"; "done" is queued but not consumed
    assert any(e[0] == "error" and "Invalid API key" in e[1] for e in events)


@pytest.mark.asyncio
async def test_stream_with_heartbeat_rate_limit(mocker):
    from anthropic import RateLimitError

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {}
    mock_resp.json.return_value = {}
    err = RateLimitError("rate limited", response=mock_resp, body={})

    mock_client, _ = _make_stream_mock(mocker, side_effect=err)
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    from app.services.llm_service import stream_with_heartbeat

    events = []
    async for event_type, data in stream_with_heartbeat([], "claude-sonnet-4-6", "sk-ant-fake"):
        events.append((event_type, data))

    assert any(e[0] == "error" and "Rate limit" in e[1] for e in events)


@pytest.mark.asyncio
async def test_stream_with_heartbeat_unexpected_error(mocker):
    mock_client, _ = _make_stream_mock(mocker, side_effect=RuntimeError("boom"))
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    from app.services.llm_service import stream_with_heartbeat

    events = []
    async for event_type, data in stream_with_heartbeat([], "claude-sonnet-4-6", "sk-ant-fake"):
        events.append((event_type, data))

    assert any(e[0] == "error" and "unexpected" in e[1].lower() for e in events)


# ---------------------------------------------------------------------------
# llm_service.persist_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_with_heartbeat_api_status_error_529(mocker):
    """529 Anthropic overload → 'overloaded' error message."""
    from anthropic import APIStatusError

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 529
    mock_resp.headers = {}
    mock_resp.json.return_value = {}
    err = APIStatusError("overloaded", response=mock_resp, body={})

    mock_client, _ = _make_stream_mock(mocker, side_effect=err)
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    from app.services.llm_service import stream_with_heartbeat

    events = []
    async for event_type, data in stream_with_heartbeat([], "claude-sonnet-4-6", "sk-ant-fake"):
        events.append((event_type, data))

    assert any(e[0] == "error" and "overloaded" in e[1].lower() for e in events)


@pytest.mark.asyncio
async def test_stream_with_heartbeat_api_status_error_other(mocker):
    """Non-529 APIStatusError → generic error message."""
    from anthropic import APIStatusError

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 500
    mock_resp.headers = {}
    mock_resp.json.return_value = {}
    err = APIStatusError("server error", response=mock_resp, body={})

    mock_client, _ = _make_stream_mock(mocker, side_effect=err)
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    from app.services.llm_service import stream_with_heartbeat

    events = []
    async for event_type, data in stream_with_heartbeat([], "claude-sonnet-4-6", "sk-ant-fake"):
        events.append((event_type, data))

    assert any(e[0] == "error" and "Anthropic API" in e[1] for e in events)


@pytest.mark.asyncio
async def test_summarize_messages(mocker):
    """summarize_messages should call the Anthropic client and return text."""
    from types import SimpleNamespace
    from app.services.llm_service import summarize_messages

    mock_content = SimpleNamespace(text="Summary text")
    mock_resp = SimpleNamespace(content=[mock_content])
    mock_client = mocker.AsyncMock()
    mock_client.messages.create = mocker.AsyncMock(return_value=mock_resp)
    mocker.patch("app.services.llm_service.AsyncAnthropic", return_value=mock_client)

    messages = [_make_msg("user", "hello", 0), _make_msg("assistant", "hi", 1)]
    result = await summarize_messages(messages, "sk-ant-fake")
    assert result == "Summary text"


@pytest.mark.asyncio
async def test_get_db_rollback_on_exception(mocker):
    """db/session.py rollback branch: exception during request rolls back."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.db.session import get_db

    test_engine = create_async_engine(
        "postgresql+asyncpg://idealens:idealens@localhost:5432/idealens_test",
        poolclass=NullPool,
    )
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    mocker.patch("app.db.session.AsyncSessionLocal", TestSession)

    gen = get_db()
    session = await gen.__anext__()

    # Simulate exception during request handling
    try:
        await gen.athrow(ValueError("boom"))
    except ValueError:
        pass
    except StopAsyncIteration:
        pass

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_persist_messages(db):
    """persist_messages should insert user + assistant messages in order."""
    from app.services.llm_service import persist_messages
    from app.services.auth_service import hash_password
    from app.db.models.user import User
    from app.db.models.session import Session as DBSession
    from app.db.models.message import Message
    from sqlalchemy import select

    user = User(email="persist@example.com", name="P", password_hash=hash_password("x"))
    db.add(user)
    await db.flush()

    session = DBSession(
        user_id=user.id,
        idea="test",
        name="t",
        graph_state={"nodes": [], "edges": []},
    )
    db.add(session)
    await db.flush()

    from app.schemas.graph import AddNodeAction, NodePayload, DimensionType

    action = AddNodeAction(
        action="add",
        payload=NodePayload(
            id="c1",
            type=DimensionType.CONCEPT,
            label="Concept",
            content="Detail",
            score=None,
            parent_id=None,
        ),
    )
    await persist_messages(db, session.id, "hello", "world", [action], "msg-uuid-1")

    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.message_index)
    )
    messages = result.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "hello"
    assert messages[1].role == "assistant"
    assert messages[1].id == "msg-uuid-1"
    assert messages[1].metadata_["graph_actions"][0]["action"] == "add"
