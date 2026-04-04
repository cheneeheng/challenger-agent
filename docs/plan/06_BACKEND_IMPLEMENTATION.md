# BACKEND IMPLEMENTATION REFERENCE
> Authoritative implementation guide for the Python + FastAPI backend.
> Claude Code: read this before implementing any backend component.

---

## 1. Project Bootstrap

```bash
cd apps/api
uv init
uv venv
uv add fastapi uvicorn[standard] pydantic[email] pydantic-settings structlog \
       sqlalchemy[asyncio] asyncpg alembic \
       python-jose[cryptography] passlib[bcrypt] python-multipart \
       cryptography anthropic slowapi
uv add --dev pytest pytest-asyncio httpx ruff mypy
```

`pyproject.toml` tool config:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

---

## 2. Settings (`app/config.py`)

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str                   # postgresql+asyncpg://user:pass@host/db

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption (Fernet key — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    API_KEY_ENCRYPTION_KEY: str

    # App
    FRONTEND_URL: str
    ENVIRONMENT: str = "development"    # "development" | "production"

    # LLM
    ALLOWED_CLAUDE_MODELS: list[str] = [
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
        "claude-opus-4-6",
    ]
    DEFAULT_MODEL: str = "claude-sonnet-4-6"
    CONTEXT_WINDOW_MAX_MESSAGES: int = 20

    # Test DB (only for pytest)
    TEST_DATABASE_URL: str = ""

    # Seed (optional — pre-sets test user's API key if provided)
    SEED_ANTHROPIC_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`.env.example`:
```bash
DATABASE_URL=postgresql+asyncpg://idealens:idealens@localhost:5432/idealens
JWT_SECRET=change-me-generate-with-secrets-token-hex-64
JWT_ALGORITHM=HS256
API_KEY_ENCRYPTION_KEY=  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
TEST_DATABASE_URL=postgresql+asyncpg://idealens:idealens@localhost:5432/idealens_test
SEED_ANTHROPIC_API_KEY=  # optional
```

---

## 3. FastAPI App Factory — Middleware Order (`app/main.py`)

Middleware order is critical. In FastAPI/Starlette, middleware is applied in reverse order (last added = outermost). To ensure CORS handles OPTIONS preflight before security headers intercept it:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from app.config import get_settings
from app.api.routes import auth, users, sessions, chat, models as models_router

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if get_settings().ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.base import engine
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))  # verify DB on startup
    yield
    await engine.dispose()

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="IdeaLens API",
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # MIDDLEWARE ORDER — add in reverse of desired execution order:
    # Desired: SecurityHeaders(outermost) → CORS → routes
    # Therefore add CORS first, SecurityHeaders second:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,     # required for httpOnly cookie to be sent
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)  # added last = outermost

    # Rate limiter
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Routers
    app.include_router(auth.router, tags=["auth"])
    app.include_router(users.router, tags=["users"])
    app.include_router(sessions.router, tags=["sessions"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(models_router.router, tags=["models"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    return app

app = create_app()
```

---

## 4. Database — Async Engine + Session

```python
# app/db/base.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import get_settings

engine = create_async_engine(
    get_settings().DATABASE_URL,
    echo=get_settings().ENVIRONMENT == "development",
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# app/db/session.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## 5. Alembic Async Configuration

This is the most common source of errors when setting up SQLAlchemy async + Alembic. Follow exactly.

`alembic.ini` — set sqlalchemy.url to a placeholder (real URL comes from env.py):
```ini
[alembic]
script_location = alembic
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
sqlalchemy.url = postgresql+asyncpg://placeholder
```

`alembic/env.py` — full async implementation:
```python
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and ALL models — __init__.py registers them all
from app.db.models.base import Base
import app.db.models  # noqa: F401 — side effect: registers all model classes

target_metadata = Base.metadata

def get_url() -> str:
    from app.config import get_settings
    return get_settings().DATABASE_URL

def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

`app/db/models/__init__.py` — must exist and import all models:
```python
# This file must import all models so Alembic autogenerate can discover them.
from app.db.models.user import User              # noqa: F401
from app.db.models.refresh_token import RefreshToken  # noqa: F401
from app.db.models.session import Session        # noqa: F401
from app.db.models.message import Message        # noqa: F401
```

---

## 6. Database Models

```python
# app/db/models/base.py
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass

# app/db/models/user.py
from uuid import uuid4
from datetime import datetime
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

# app/db/models/refresh_token.py
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

# app/db/models/session.py
from sqlalchemy import JSON, ForeignKey
class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String, default="Untitled Analysis")
    idea: Mapped[str] = mapped_column(String, nullable=False)
    graph_state: Mapped[dict] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": []})
    selected_model: Mapped[str] = mapped_column(String, default="claude-sonnet-4-6")
    context_summary: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    context_summary_covers_up_to: Mapped[int | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="Message.message_index"
    )

# app/db/models/message.py
class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)   # 'user' | 'assistant' | 'system'
    content: Mapped[str] = mapped_column(String, nullable=False)
    message_index: Mapped[int] = mapped_column(nullable=False)
    # Use metadata_ to avoid collision with SQLAlchemy's reserved .metadata attribute
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    session: Mapped["Session"] = relationship(back_populates="messages")
```

---

## 7. Auth Service + Cookie Spec

```python
# app/services/auth_service.py
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": exp, "type": "refresh"}, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)

def verify_token(token: str, expected_type: str = "access") -> str:
    """Returns user_id. Raises JWTError on invalid/expired token."""
    s = get_settings()
    payload = jwt.decode(token, s.JWT_SECRET, algorithms=[s.JWT_ALGORITHM])
    if expected_type == "refresh" and payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    user_id = payload.get("sub")
    if not user_id:
        raise JWTError("Missing sub claim")
    return user_id
```

**Refresh token cookie — must be set identically in both register AND login responses:**
```python
def set_refresh_cookie(response: Response, token: str) -> None:
    """Call this in both /auth/register and /auth/login."""
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",  # False locally (no HTTPS)
        samesite="strict",
        max_age=60 * 60 * 24 * settings.REFRESH_TOKEN_EXPIRE_DAYS,
        path="/auth",   # cookie only sent to /auth/* routes — minimizes exposure
    )

def clear_refresh_cookie(response: Response) -> None:
    """Call this in /auth/logout."""
    response.delete_cookie(key="refresh_token", path="/auth")
```

---

## 8. API Key Encryption Service

```python
# app/services/encryption_service.py
from cryptography.fernet import Fernet
from app.config import get_settings

def _fernet() -> Fernet:
    return Fernet(get_settings().API_KEY_ENCRYPTION_KEY.encode())

def encrypt_api_key(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()

def decrypt_api_key(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
```

API key validation before saving:
```python
# In POST /api/users/me/api-key route:
import anthropic

async def validate_api_key(api_key: str) -> None:
    """Raises HTTPException(422) if key is invalid."""
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        await client.models.list()
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=422, detail="Invalid Anthropic API key")
    except Exception:
        raise HTTPException(status_code=422, detail="Could not validate API key. Check your connection.")
```

---

## 9. LLM Service

```python
# app/services/llm_service.py
import asyncio, json, re
from anthropic import AsyncAnthropic, AuthenticationError, RateLimitError, APIStatusError
from pydantic import TypeAdapter, ValidationError
from app.schemas.graph import LLMResponse, LLMGraphAction
from app.db.models.message import Message
from app.schemas.graph import AnalysisGraph
from app.config import get_settings

GRAPH_ACTIONS_RE = re.compile(r'<GRAPH_ACTIONS>(.*?)</GRAPH_ACTIONS>', re.DOTALL)
_action_adapter = TypeAdapter(LLMGraphAction)

def build_messages(
    messages: list[Message],
    graph_state: AnalysisGraph,
    user_message: str,
    context_summary: str | None = None,
    context_summary_covers_up_to: int | None = None,
) -> list[dict]:
    settings = get_settings()
    result = []

    if context_summary and context_summary_covers_up_to is not None:
        result.append({"role": "user",      "content": f"[Previous conversation summary]: {context_summary}"})
        result.append({"role": "assistant", "content": "Understood. Continuing from the summary."})
        # context_summary_covers_up_to is the message_index (not count) of the last summarized message.
        # Include only messages with index GREATER than what was summarized.
        messages = [m for m in messages if m.message_index > context_summary_covers_up_to]

    recent = messages[-settings.CONTEXT_WINDOW_MAX_MESSAGES:]
    for m in recent:
        if m.role == "assistant":
            result.append({"role": "assistant", "content": m.content})
        else:
            prefix = "[Context]: " if m.role == "system" else ""
            result.append({"role": "user", "content": f"{prefix}{m.content}"})

    result.append({"role": "user", "content": f"[Current graph state]:\n{graph_state.model_dump_json(indent=2)}"})
    result.append({"role": "user", "content": user_message})
    return result

async def stream_with_heartbeat(messages: list[dict], model: str, api_key: str):
    """Async generator yielding (event_type, data) tuples. Uses queue for clean heartbeat."""
    from app.prompts.analysis_system import SYSTEM_PROMPT
    queue: asyncio.Queue = asyncio.Queue()
    full_text = ""

    async def llm_producer():
        nonlocal full_text
        try:
            client = AsyncAnthropic(api_key=api_key)
            async with client.messages.stream(
                model=model, max_tokens=4096, system=SYSTEM_PROMPT, messages=messages
            ) as stream:
                async for chunk in stream.text_stream:
                    full_text += chunk
                    await queue.put(("token", chunk))
            llm_response = parse_llm_response(full_text)
            await queue.put(("parsed", llm_response))
        except AuthenticationError:
            await queue.put(("error", "Invalid API key. Please update it in Settings."))
        except RateLimitError:
            await queue.put(("error", "Rate limit reached. Please wait a moment."))
        except APIStatusError as e:
            msg = "Anthropic is overloaded. Please try again." if e.status_code == 529 else "An error occurred."
            await queue.put(("error", msg))
        except Exception:
            await queue.put(("error", "An unexpected error occurred."))
        finally:
            await queue.put(("done", None))

    async def ping_producer():
        while True:
            await asyncio.sleep(15)
            await queue.put(("ping", None))

    llm_task = asyncio.create_task(llm_producer())
    ping_task = asyncio.create_task(ping_producer())
    try:
        while True:
            event_type, data = await queue.get()
            yield event_type, data
            if event_type in ("done", "error"):
                break
    finally:
        ping_task.cancel()
        llm_task.cancel()

def parse_llm_response(raw_text: str) -> LLMResponse:
    match = GRAPH_ACTIONS_RE.search(raw_text)
    natural_language = GRAPH_ACTIONS_RE.sub("", raw_text).strip()
    if not match:
        return LLMResponse(message=natural_language, graph_actions=[])
    try:
        raw_actions = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return LLMResponse(message=natural_language, graph_actions=[])
    valid = []
    for raw in raw_actions:
        try:
            valid.append(_action_adapter.validate_python(raw))
        except ValidationError:
            pass
    return LLMResponse(message=natural_language, graph_actions=valid)

async def summarize_messages(messages: list[Message], api_key: str) -> str:
    client = AsyncAnthropic(api_key=api_key)
    content = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
    resp = await client.messages.create(
        model="claude-haiku-4-5",  # always haiku — cheapest
        max_tokens=1024,
        messages=[{"role": "user", "content":
            f"Summarize concisely. Preserve key decisions, insights, node modifications, open questions.\n\n{content}"
        }],
    )
    return resp.content[0].text
```

---

## 10. Message Persistence — Concurrency-Safe Index Assignment

Using `SELECT FOR UPDATE` prevents two concurrent requests from getting the same `message_index`:

```python
async def persist_messages(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    assistant_text: str,
    graph_actions: list,
    message_uuid: str,
) -> None:
    from sqlalchemy import select, func
    from app.db.models.message import Message

    async with db.begin():
        result = await db.execute(
            select(func.max(Message.message_index))
            .where(Message.session_id == session_id)
            .with_for_update()  # locks the row to prevent concurrent index collision
        )
        max_index = result.scalar() or -1

        db.add(Message(
            session_id=session_id,
            role="user",
            content=user_message,
            message_index=max_index + 1,
        ))
        db.add(Message(
            id=message_uuid,    # use SSE event UUID as message ID for reconnection replay
            session_id=session_id,
            role="assistant",
            content=assistant_text,
            message_index=max_index + 2,
            metadata_={"graph_actions": [a.model_dump() for a in graph_actions]},
        ))
```

---

## 11. Session Creation — Root Node Initialization

When `POST /api/sessions` is called, `graph_state` is pre-populated with the root node. The LLM never creates or modifies this node.

```python
# In POST /api/sessions route:
def build_initial_graph(idea: str) -> dict:
    return {
        "nodes": [{
            "id": "root",
            "type": "root",
            "label": idea[:80],   # truncate for display
            "content": idea,
            "score": None,
            "parent_id": None,
            "position": {"x": 400, "y": 300},   # centered; will be re-laid out by Dagre
            "userPositioned": False,
        }],
        "edges": []
    }

# In route handler:
session = Session(
    user_id=current_user.id,
    idea=body.idea,
    name=body.idea[:60],
    selected_model=body.selected_model,
    graph_state=build_initial_graph(body.idea),
)
```

---

## 12. SSE Streaming Endpoint

```python
# app/api/routes/chat.py
import json
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.auth import get_current_user
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.session import Session as DBSession
from app.schemas.chat import ChatRequest
from app.services import llm_service, encryption_service

router = APIRouter()

@router.post("/api/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(DBSession, body.session_id)
    if not session or session.user_id != current_user.id:
        # 403 not 404 — prevents session ID enumeration
        async def forbidden():
            yield "event: error\ndata: Session not found.\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        return StreamingResponse(forbidden(), media_type="text/event-stream")

    if not current_user.encrypted_api_key:
        async def no_key():
            yield "event: error\ndata: Please set your Anthropic API key in Settings.\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        return StreamingResponse(no_key(), media_type="text/event-stream")

    api_key = encryption_service.decrypt_api_key(current_user.encrypted_api_key)

    # SSE reconnection check
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        from sqlalchemy import select
        from app.db.models.message import Message
        result = await db.execute(
            select(Message).where(
                Message.id == last_event_id,
                Message.role == "assistant",
                Message.session_id == body.session_id,
            )
        )
        completed = result.scalar_one_or_none()
        if completed:
            # Message already persisted — replay without calling LLM again
            return StreamingResponse(
                _replay_completed(completed),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        # Not found: partial response was lost — fall through to fresh start

    # Context management
    settings = get_settings()
    messages = session.messages
    if len(messages) > settings.CONTEXT_WINDOW_MAX_MESSAGES and not session.context_summary:
        to_summarize = messages[:-settings.CONTEXT_WINDOW_MAX_MESSAGES]
        summary = await llm_service.summarize_messages(to_summarize, api_key)
        session.context_summary = summary
        # Store the message_index of the last summarized message (not the count).
        # build_messages filters with m.message_index > this value.
        session.context_summary_covers_up_to = to_summarize[-1].message_index
        await db.commit()

    llm_messages = llm_service.build_messages(
        messages=session.messages,
        graph_state=body.graph_state,
        user_message=body.message,
        context_summary=session.context_summary,
        context_summary_covers_up_to=session.context_summary_covers_up_to,
    )

    message_uuid = str(uuid4())

    return StreamingResponse(
        _stream(db, session, body, llm_messages, api_key, message_uuid),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

async def _stream(db, session, body, llm_messages, api_key, message_uuid):
    full_text = ""
    graph_actions = []
    had_error = False

    async for event_type, data in llm_service.stream_with_heartbeat(llm_messages, body.model, api_key):
        if event_type == "token":
            full_text += data
            yield f"id: {message_uuid}\nevent: token\ndata: {data}\n\n"
        elif event_type == "parsed":
            graph_actions = data.graph_actions
            for action in data.graph_actions:
                yield f"id: {message_uuid}\nevent: graph_action\ndata: {json.dumps(action.model_dump())}\n\n"
        elif event_type == "ping":
            yield "event: ping\ndata: \n\n"
        elif event_type == "error":
            had_error = True
            yield f"event: error\ndata: {data}\n\n"
        elif event_type == "done":
            break

    if not had_error:
        await llm_service.persist_messages(db, session.id, body.message, full_text, graph_actions, message_uuid)

    yield f"id: {message_uuid}\nevent: done\ndata: [DONE]\n\n"


async def _replay_completed(message):
    """Replay a previously completed response without calling the LLM again."""
    import json
    actions = (message.metadata_ or {}).get("graph_actions", [])
    for action in actions:
        yield f"id: {message.id}\nevent: graph_action\ndata: {json.dumps(action)}\n\n"
    yield f"id: {message.id}\nevent: done\ndata: [DONE]\n\n"
```

---

## 13. pytest conftest.py

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.main import app
from app.db.models.base import Base
import app.db.models  # noqa — register all models
from app.db.session import get_db
from app.config import get_settings

settings = get_settings()
TEST_ENGINE = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)

# CRITICAL: Override get_settings() in tests so lru_cache doesn't return the
# production Settings instance (which reads from .env). Tests must use TEST_DATABASE_URL.
@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """Ensure all routes use test database. Must run before any DB fixture."""
    from app.config import get_settings as _get_settings
    test_settings = _get_settings()
    # Override DATABASE_URL to point at test DB
    object.__setattr__(test_settings, 'DATABASE_URL', test_settings.TEST_DATABASE_URL)
    yield

@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await TEST_ENGINE.dispose()

@pytest.fixture(autouse=True)
async def db_session():
    """Each test wrapped in a rolled-back transaction — no data leaks between tests."""
    async with TEST_ENGINE.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        app.dependency_overrides[get_db] = lambda: session
        yield session
        await session.close()
        await conn.rollback()
    app.dependency_overrides.clear()

@pytest.fixture
async def client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.fixture
async def test_user(client) -> dict:
    resp = await client.post("/auth/register", json={
        "email": "test@test.com", "name": "Test", "password": "testpass123"
    })
    assert resp.status_code == 200
    return {"token": resp.json()["access_token"], "email": "test@test.com"}

@pytest.fixture
async def authed_client(client, test_user):
    client.headers.update({"Authorization": f"Bearer {test_user['token']}"})
    return client

@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patches Anthropic SDK — no real API calls in tests."""
    FAKE_RESPONSE = (
        '<GRAPH_ACTIONS>[{"action":"add","payload":{"id":"n1","type":"concept",'
        '"label":"Test","content":"Content","score":null,"parent_id":null}}]</GRAPH_ACTIONS>'
        '\nHere is my analysis.'
    )

    class FakeTextStream:
        async def __aiter__(self):
            yield FAKE_RESPONSE

    class FakeStream:
        text_stream = FakeTextStream()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeMessages:
        def stream(self, **kwargs): return FakeStream()

    class FakeModels:
        async def list(self): return []

    class FakeClient:
        messages = FakeMessages()
        models = FakeModels()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **kw: FakeClient())
    return FakeClient()
```

---

## 14. Rate Limiting Per-User for Chat

```python
# Per-user rate limiting for /api/chat (not per-IP, which would be unfair in shared environments)
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_user_identifier(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.services.auth_service import verify_token
            return f"user:{verify_token(auth[7:])}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"

user_limiter = Limiter(key_func=get_user_identifier)

# Apply to chat route:
@router.post("/api/chat")
@user_limiter.limit("30/minute")
async def chat(request: Request, ...):
```

---

## 15. Seed Script

```python
# app/db/seed.py
"""
Idempotent seed script for local development.
Usage: docker-compose exec api python -m app.db.seed
Creates: test user + sample session with pre-built graph covering all 9 dimension types.
"""
import asyncio
from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.session import Session
from app.services.auth_service import hash_password
from app.services.encryption_service import encrypt_api_key
from app.config import get_settings

SEED_EMAIL    = "test@idealens.dev"
SEED_PASSWORD = "testpass123"
SEED_IDEA     = "Build a SaaS product for restaurant inventory management"

# Pre-built graph with nodes for all 9 dimension types — no LLM call needed
SEED_GRAPH = {
    "nodes": [
        {"id": "root",        "type": "root",        "label": SEED_IDEA[:60],              "content": SEED_IDEA,             "score": None, "parent_id": None, "position": {"x": 400, "y": 50},  "userPositioned": False},
        {"id": "concept-1",   "type": "concept",     "label": "Digital inventory platform", "content": "A cloud-based system that tracks stock levels, supplier orders, and waste in real time for restaurants.", "score": None, "parent_id": "root",  "position": {"x": 200, "y": 200}, "userPositioned": False},
        {"id": "req-1",       "type": "requirement", "label": "POS integration",            "content": "Must integrate with existing POS systems (Square, Toast, etc.) to auto-deduct inventory.", "score": None, "parent_id": None, "position": {"x": 600, "y": 200}, "userPositioned": False},
        {"id": "gap-1",       "type": "gap",         "label": "Supplier API access",        "content": "Many small suppliers lack APIs; manual data entry may be required.", "score": None, "parent_id": None, "position": {"x": 100, "y": 350}, "userPositioned": False},
        {"id": "benefit-1",   "type": "benefit",     "label": "Reduces food waste",         "content": "Real-time tracking can reduce food waste by 20-30%, directly improving margins.", "score": None, "parent_id": None, "position": {"x": 300, "y": 350}, "userPositioned": False},
        {"id": "drawback-1",  "type": "drawback",    "label": "High onboarding friction",   "content": "Restaurant staff turnover is high; complex tools are often abandoned.", "score": None, "parent_id": None, "position": {"x": 500, "y": 350}, "userPositioned": False},
        {"id": "feasib-1",    "type": "feasibility", "label": "Feasibility Score: 6/10",    "content": "Market exists but is competitive. Success depends on ease of POS integration.", "score": 6.0, "parent_id": None, "position": {"x": 700, "y": 350}, "userPositioned": False},
        {"id": "flaw-1",      "type": "flaw",        "label": "Niche market size",          "content": "Targeting only restaurants limits TAM. Consider pivoting to 'food service operations'.", "score": None, "parent_id": None, "position": {"x": 100, "y": 500}, "userPositioned": False},
        {"id": "alt-1",       "type": "alternative", "label": "White-label for POS vendors", "content": "Instead of a standalone product, license the inventory module to existing POS companies.", "score": None, "parent_id": None, "position": {"x": 400, "y": 500}, "userPositioned": False},
        {"id": "question-1",  "type": "question",    "label": "Pricing model?",             "content": "Per-location SaaS fee vs percentage of waste saved? The latter aligns incentives better.", "score": None, "parent_id": None, "position": {"x": 700, "y": 500}, "userPositioned": False},
    ],
    "edges": [
        {"id": "e1", "source": "root",       "target": "concept-1",  "label": "is",        "type": "leads_to"},
        {"id": "e2", "source": "concept-1",  "target": "req-1",      "label": "needs",     "type": "requires"},
        {"id": "e3", "source": "concept-1",  "target": "benefit-1",  "label": "creates",   "type": "leads_to"},
        {"id": "e4", "source": "req-1",      "target": "gap-1",      "label": "exposes",   "type": "leads_to"},
        {"id": "e5", "source": "drawback-1", "target": "flaw-1",     "label": "compounds", "type": "supports"},
        {"id": "e6", "source": "flaw-1",     "target": "alt-1",      "label": "motivates", "type": "leads_to"},
    ]
}

async def seed():
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == SEED_EMAIL))
        if existing.scalar_one_or_none():
            print("Already seeded — skipping.")
            return

        user = User(
            email=SEED_EMAIL,
            name="Test User",
            password_hash=hash_password(SEED_PASSWORD),
            encrypted_api_key=(
                encrypt_api_key(settings.SEED_ANTHROPIC_API_KEY)
                if settings.SEED_ANTHROPIC_API_KEY else None
            ),
        )
        db.add(user)
        await db.flush()

        db.add(Session(
            user_id=user.id,
            name="Restaurant Inventory SaaS",
            idea=SEED_IDEA,
            graph_state=SEED_GRAPH,
            selected_model="claude-sonnet-4-6",
        ))
        await db.commit()

    print(f"✓ Seeded: {SEED_EMAIL} / {SEED_PASSWORD}")
    if not settings.SEED_ANTHROPIC_API_KEY:
        print("  ⚠ No SEED_ANTHROPIC_API_KEY set — user has no API key (must set in /settings)")

if __name__ == "__main__":
    asyncio.run(seed())
```