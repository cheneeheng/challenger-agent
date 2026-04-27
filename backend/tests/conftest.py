"""
Shared pytest fixtures.

Isolation strategy:
  - Session-scoped sync fixture: create all tables once per run using
    asyncio.run() so there are no cross-loop issues.
  - Function-scoped db: create a fresh NullPool engine + connection per
    test; the session uses create_savepoint mode so its commits become
    SAVEPOINTs, and we roll back the outer transaction after each test.
  - The FastAPI app's lifespan does a SELECT 1 against the prod engine
    (read-only, harmless), while route DB calls go through the overridden
    get_db dependency that uses the per-test session.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.models.base import Base
from app.db.session import get_db
from app.services.auth_service import create_access_token, hash_password


TEST_DB_URL = (
    "postgresql+asyncpg://idealens:idealens@localhost:5432/idealens_test"
)

TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = "SecurePass123!"
TEST_USER_NAME = "Test User"


# ---------------------------------------------------------------------------
# Session-scoped: create schema once (sync so no cross-loop issues)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    async def _setup():
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())


# ---------------------------------------------------------------------------
# Function-scoped: isolated DB session per test (NullPool, rolled back)
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    """
    Yield an AsyncSession backed by a rolled-back connection.
    Each test gets its own asyncpg connection; nothing is persisted.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    conn = await engine.connect()
    await conn.begin()
    session = AsyncSession(
        conn,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        await session.close()
        await conn.rollback()
        await conn.close()
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------


@pytest.fixture
def test_app(db: AsyncSession):
    from app.main import create_app

    _app = create_app()

    async def _override_get_db():
        yield db

    _app.dependency_overrides[get_db] = _override_get_db
    return _app


@pytest.fixture
async def client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Pre-seeded user + auth helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_user(db: AsyncSession):
    """Create a user directly in the DB, bypassing the HTTP layer."""
    from app.db.models.user import User

    user = User(
        email=TEST_USER_EMAIL,
        name=TEST_USER_NAME,
        password_hash=hash_password(TEST_USER_PASSWORD),
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_session(db: AsyncSession, test_user):
    """Create an analysis session for test_user."""
    from app.db.models.session import Session as DBSession

    session = DBSession(
        user_id=test_user.id,
        idea="Test idea for unit tests",
        name="Test Session",
        selected_model="claude-sonnet-4-6",
        graph_state={
            "nodes": [
                {
                    "id": "root",
                    "type": "root",
                    "label": "Test idea",
                    "content": "Test idea for unit tests",
                    "score": None,
                    "parent_id": None,
                    "position": {"x": 400, "y": 300},
                    "userPositioned": False,
                }
            ],
            "edges": [],
        },
    )
    db.add(session)
    await db.flush()
    return session
