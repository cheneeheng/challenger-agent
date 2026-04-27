---
doc: 06_BACKEND_IMPLEMENTATION_GOOGLE
status: ready
version: 1
created: 2026-04-18
scope: Google GenAI SDK alternative — provider abstraction, Google-specific LLM service, settings changes, DB migration, API key route changes, test fixtures. Read alongside 06_BACKEND_IMPLEMENTATION.md.
relates_to:
  - 06_BACKEND_IMPLEMENTATION
  - 03_ARCHITECTURE
  - 04_LIBRARIES_AND_FRAMEWORKS
  - 08_LLM_AND_PROMPT
---
# BACKEND — GOOGLE GENAI SDK VARIANT

Claude Code: read this before implementing any backend component.

**Stack:** Python 3.12 · FastAPI · PostgreSQL · SQLAlchemy 2.x async · Pydantic v2 · Anthropic SDK · Google GenAI SDK · Fernet · JWT · pytest

> Read `06_BACKEND_IMPLEMENTATION.md` first — this doc covers only the delta.
> Everything that changes when `LLM_PROVIDER=google` is set is documented here.
> Files not listed in this doc are unchanged from the baseline and must be implemented verbatim from there.

---

## 0. Decision Log

| Decision | Rationale |
|---|---|
| `google-genai` (not `google-generativeai`) | `google-generativeai` is deprecated as of Gemini 2.0 release (late 2024). `google-genai` is the unified GA SDK for both Gemini Developer API and Vertex AI. |
| Provider strategy pattern | The chat route (`12` in `06`) and all callers import from `llm_service.py` unchanged. Switching provider = one env var. |
| `"model"` role in Google messages | Google's wire format uses `"model"` not `"assistant"`. Conversion happens inside the Google provider — the shared `build_messages()` function stays `"assistant"` throughout. |
| System prompt via `GenerateContentConfig` | Google does not accept a top-level `system` parameter like Anthropic. It goes in `config=types.GenerateContentConfig(system_instruction=...)`. |
| Summary model = `gemini-2.0-flash` | Mirrors the role of `claude-haiku-4-5` — cheapest fast model. Used only for context summarization, not the main analysis. |
| Two separate encrypted key columns | `encrypted_anthropic_api_key` and `encrypted_google_api_key` on `User`. The active provider reads only its own column. Avoids any ambiguity over what the single `encrypted_api_key` column holds. |
| `LLM_PROVIDER` is server-side only | The frontend does not know or care which provider is active. Model selector still shows the correct allowed models (served from `GET /api/models`). |

---

## 1. Additional Dependency

```bash
uv add "google-genai[aiohttp]"
```

`[aiohttp]` installs the optional faster async transport. Without it the SDK falls back to httpx, which still works but is slower under load.

Updated dependency block in `pyproject.toml`:
```toml
[project]
dependencies = [
    # ... existing deps unchanged ...
    "anthropic>=0.49",
    "google-genai[aiohttp]>=1.0",
]
```

---

## 2. File Structure — New Files

```
apps/api/app/services/
├── llm_service.py               ← MODIFIED (becomes a thin router)
├── llm_helpers.py               ← NEW (shared parse logic extracted from llm_service.py)
├── encryption_service.py        ← UNCHANGED
└── providers/
    ├── __init__.py              ← NEW (empty)
    ├── base.py                  ← NEW (abstract contract)
    ├── anthropic_provider.py    ← NEW (Anthropic logic moved from llm_service.py verbatim)
    └── google_provider.py       ← NEW (Google GenAI implementation)
```

All other files (`auth_service.py`, `encryption_service.py`, all routes, all models) are **unchanged**.

---

## 3. Settings Changes (`app/config.py`)

Replace the `# LLM` block and the `SEED_ANTHROPIC_API_KEY` field. Everything else in `Settings` is unchanged.

```python
class Settings(BaseSettings):
    # ... all existing fields unchanged above this line ...

    # LLM — Provider selection
    LLM_PROVIDER: str = "anthropic"          # "anthropic" | "google"

    # Anthropic models
    ALLOWED_ANTHROPIC_MODELS: list[str] = [
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
        "claude-opus-4-6",
    ]
    DEFAULT_ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # Google Gemini models
    ALLOWED_GOOGLE_MODELS: list[str] = [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]
    DEFAULT_GOOGLE_MODEL: str = "gemini-2.5-flash"

    CONTEXT_WINDOW_MAX_MESSAGES: int = 20    # unchanged

    # Seed keys (optional — both can coexist; only the active provider's key is used)
    SEED_ANTHROPIC_API_KEY: str = ""
    SEED_GOOGLE_API_KEY: str = ""

    # Computed helpers — used by GET /api/models and session creation validation
    @property
    def ALLOWED_MODELS(self) -> list[str]:
        return (
            self.ALLOWED_GOOGLE_MODELS
            if self.LLM_PROVIDER == "google"
            else self.ALLOWED_ANTHROPIC_MODELS
        )

    @property
    def DEFAULT_MODEL(self) -> str:
        return (
            self.DEFAULT_GOOGLE_MODEL
            if self.LLM_PROVIDER == "google"
            else self.DEFAULT_ANTHROPIC_MODEL
        )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

> **Note on `lru_cache`:** `@property` fields are not included in Pydantic's model hash, so `get_settings()` with `@lru_cache` continues to work correctly. The properties are computed from the cached instance on each access.

Updated `.env.example` additions:
```bash
# LLM Provider — which SDK to use ("anthropic" default, or "google")
LLM_PROVIDER=anthropic

# Used when LLM_PROVIDER=anthropic (unchanged)
SEED_ANTHROPIC_API_KEY=  # optional

# Used when LLM_PROVIDER=google
SEED_GOOGLE_API_KEY=     # optional — get from https://aistudio.google.com/apikey
```

---

## 4. Database Migration — Two API Key Columns

The existing `User` model has a single `encrypted_api_key: str | None` column. This must be renamed and a second column added.

### 4a. Updated `User` model (`app/db/models/user.py`)

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    # Provider-specific encrypted API keys — both nullable; only active provider's column populated
    encrypted_anthropic_api_key: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    encrypted_google_api_key: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

### 4b. Alembic migration

```bash
alembic revision --autogenerate -m "split_api_key_columns_anthropic_google"
```

The autogenerated migration will drop `encrypted_api_key` and add the two new columns. **Before running:** if you have existing users with populated `encrypted_api_key`, write a data migration step inside the revision to copy values to `encrypted_anthropic_api_key` first:

```python
# In the generated revision file — add this BEFORE the column drop:
def upgrade() -> None:
    # 1. Add new columns
    op.add_column("users", sa.Column("encrypted_anthropic_api_key", sa.String(), nullable=True))
    op.add_column("users", sa.Column("encrypted_google_api_key", sa.String(), nullable=True))
    # 2. Migrate existing data
    op.execute("UPDATE users SET encrypted_anthropic_api_key = encrypted_api_key WHERE encrypted_api_key IS NOT NULL")
    # 3. Drop old column
    op.drop_column("users", "encrypted_api_key")

def downgrade() -> None:
    op.add_column("users", sa.Column("encrypted_api_key", sa.String(), nullable=True))
    op.execute("UPDATE users SET encrypted_api_key = encrypted_anthropic_api_key WHERE encrypted_anthropic_api_key IS NOT NULL")
    op.drop_column("users", "encrypted_anthropic_api_key")
    op.drop_column("users", "encrypted_google_api_key")
```

```bash
alembic upgrade head
```

---

## 5. API Key Route Changes (`app/api/routes/users.py`)

The `POST /api/users/me/api-key` route now accepts a `provider` field. The `GET /api/users/me` response exposes `has_anthropic_key` and `has_google_key` booleans (never the raw key).

### 5a. Request schema

```python
# app/schemas/user.py — update ApiKeyRequest
from typing import Literal
from pydantic import BaseModel

class ApiKeyRequest(BaseModel):
    api_key: str
    provider: Literal["anthropic", "google"] = "anthropic"
```

### 5b. Route handler

```python
# app/api/routes/users.py
from app.services import encryption_service
from app.services.llm_service import get_provider

@router.post("/api/users/me/api-key")
async def save_api_key(
    body: ApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate key against the correct provider SDK before saving
    await get_provider(body.provider).validate_api_key(body.api_key)

    encrypted = encryption_service.encrypt_api_key(body.api_key)

    if body.provider == "google":
        current_user.encrypted_google_api_key = encrypted
    else:
        current_user.encrypted_anthropic_api_key = encrypted

    await db.commit()
    return {"message": "API key saved successfully"}
```

> **Why `get_provider(body.provider)` instead of `get_provider()`?** The user may be saving a Google key while the server is currently set to `LLM_PROVIDER=anthropic`, or vice versa. Key validation must always use the matching SDK regardless of the server's active provider setting.

### 5c. `GET /api/users/me` response — expose both key presence flags

```python
# app/schemas/user.py — UserResponse
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    has_anthropic_key: bool
    has_google_key: bool
    has_active_key: bool   # true if the key for the currently active LLM_PROVIDER is set
    created_at: datetime

# In the route handler:
settings = get_settings()
return UserResponse(
    id=current_user.id,
    email=current_user.email,
    name=current_user.name,
    has_anthropic_key=current_user.encrypted_anthropic_api_key is not None,
    has_google_key=current_user.encrypted_google_api_key is not None,
    has_active_key=(
        current_user.encrypted_google_api_key is not None
        if settings.LLM_PROVIDER == "google"
        else current_user.encrypted_anthropic_api_key is not None
    ),
    created_at=current_user.created_at,
)
```

The `ApiKeyGuard` component checks `has_active_key` exactly as it previously checked `has_api_key` — no frontend logic change required beyond the field rename.

---

## 6. Chat Route — API Key Resolution (`app/api/routes/chat.py`)

The following are **unchanged** — implement them verbatim from `06_BACKEND_IMPLEMENTATION.md §12` and `§14`:
- `@user_limiter.limit("30/minute")` decorator and `get_user_identifier` key function (§14) — **must be kept**
- SSE reconnection check (`last-event-id` header lookup)
- `_replay_completed()` helper — unchanged; the persisted message format is provider-agnostic
- Context summarization trigger and `build_messages()` call
- `_stream()` inner generator (token/parsed/ping/error/done loop)

**Only the API key resolution block changes.** Replace this block:

```python
# REMOVE — original single-key block:
if not current_user.encrypted_api_key:
    async def no_key():
        yield "event: error\ndata: Please set your Anthropic API key in Settings.\n\n"
        yield "event: done\ndata: [DONE]\n\n"
    return StreamingResponse(no_key(), media_type="text/event-stream")
api_key = encryption_service.decrypt_api_key(current_user.encrypted_api_key)
```

With:

```python
# REPLACE WITH — provider-aware key resolution:
settings = get_settings()

if settings.LLM_PROVIDER == "google":
    if not current_user.encrypted_google_api_key:
        async def no_key():
            yield "event: error\ndata: Please set your Google API key in Settings.\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        return StreamingResponse(no_key(), media_type="text/event-stream")
    api_key = encryption_service.decrypt_api_key(current_user.encrypted_google_api_key)
else:
    if not current_user.encrypted_anthropic_api_key:
        async def no_key():
            yield "event: error\ndata: Please set your Anthropic API key in Settings.\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        return StreamingResponse(no_key(), media_type="text/event-stream")
    api_key = encryption_service.decrypt_api_key(current_user.encrypted_anthropic_api_key)
```

---

## 7. LLM Helpers — Extracted Shared Logic (`app/services/llm_helpers.py`)

`parse_llm_response` and the regex are used by both providers. Extract them so neither provider imports from the other.

```python
# app/services/llm_helpers.py
import json, re
from pydantic import TypeAdapter, ValidationError
from app.schemas.graph import LLMResponse, LLMGraphAction

GRAPH_ACTIONS_RE = re.compile(r'<GRAPH_ACTIONS>(.*?)</GRAPH_ACTIONS>', re.DOTALL)
_action_adapter = TypeAdapter(LLMGraphAction)


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
```

---

## 8. Provider Base Class (`app/services/providers/base.py`)

```python
# app/services/providers/base.py
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from app.db.models.message import Message
from app.schemas.graph import LLMResponse


class BaseLLMProvider(ABC):
    """
    Contract all LLM providers must satisfy.
    stream_with_heartbeat yields (event_type, data) tuples — same contract
    as the original llm_service.stream_with_heartbeat so callers need zero changes.
    """

    @abstractmethod
    async def stream_with_heartbeat(
        self,
        messages: list[dict],
        model: str,
        api_key: str,
    ) -> AsyncGenerator[tuple[str, object], None]:
        """
        Yields (event_type, data):
          ("token",  str)            — partial text chunk
          ("parsed", LLMResponse)    — fully parsed response after stream ends
          ("ping",   None)           — heartbeat every 15s
          ("error",  str)            — user-facing error message
          ("done",   None)           — stream complete
        """
        ...

    @abstractmethod
    async def summarize_messages(self, messages: list[Message], api_key: str) -> str:
        """Return a concise summary string for context window management."""
        ...

    @abstractmethod
    async def validate_api_key(self, api_key: str) -> None:
        """
        Probe the provider with the given key.
        Raises HTTPException(422) if invalid or unreachable.
        """
        ...
```

---

## 9. Anthropic Provider (`app/services/providers/anthropic_provider.py`)

Copy verbatim from `06_BACKEND_IMPLEMENTATION.md` §8 (validate_api_key) and §9 (LLM service). The only changes are:
- Import `parse_llm_response` from `llm_helpers` instead of defining it inline
- Inherit from `BaseLLMProvider`

```python
# app/services/providers/anthropic_provider.py
import asyncio
from collections.abc import AsyncGenerator
from fastapi import HTTPException
from anthropic import AsyncAnthropic, AuthenticationError, RateLimitError, APIStatusError

from app.services.providers.base import BaseLLMProvider
from app.services.llm_helpers import parse_llm_response
from app.db.models.message import Message


class AnthropicProvider(BaseLLMProvider):

    async def stream_with_heartbeat(
        self, messages: list[dict], model: str, api_key: str
    ) -> AsyncGenerator[tuple[str, object], None]:
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
                await queue.put(("parsed", parse_llm_response(full_text)))
            except AuthenticationError:
                await queue.put(("error", "Invalid API key. Please update it in Settings."))
            except RateLimitError:
                await queue.put(("error", "Rate limit reached. Please wait a moment."))
            except APIStatusError as e:
                msg = (
                    "Anthropic is overloaded. Please try again."
                    if e.status_code == 529 else "An error occurred."
                )
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

    async def summarize_messages(self, messages: list[Message], api_key: str) -> str:
        client = AsyncAnthropic(api_key=api_key)
        content = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content":
                f"Summarize concisely. Preserve key decisions, insights, "
                f"node modifications, open questions.\n\n{content}"
            }],
        )
        return resp.content[0].text

    async def validate_api_key(self, api_key: str) -> None:
        try:
            client = AsyncAnthropic(api_key=api_key)
            await client.models.list()
        except AuthenticationError:
            raise HTTPException(status_code=422, detail="Invalid Anthropic API key")
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Could not validate Anthropic API key. Check your connection."
            )
```

---

## 10. Google Provider (`app/services/providers/google_provider.py`)

### Key differences from Anthropic

| Concern | Anthropic | Google |
|---|---|---|
| Message role for LLM reply | `"assistant"` | `"model"` |
| System prompt | `system=` top-level param | `config=GenerateContentConfig(system_instruction=...)` |
| Streaming call | `client.messages.stream(...)` async context manager | `await client.aio.models.generate_content_stream(...)` async iterator |
| Chunk text access | `chunk` is a string directly | `chunk.text` — can be `None` on non-text chunks, must guard |
| Auth error class | `anthropic.AuthenticationError` | `google.genai.errors.ClientError` with `.status_code` 401/403 |
| Rate limit error | `anthropic.RateLimitError` | `google.genai.errors.ClientError` with `.status_code` 429 |
| Server overload | `APIStatusError` with `.status_code` 529 | `google.genai.errors.ServerError` |
| Key validation probe | `client.models.list()` | `client.aio.models.list()` |
| Summary model | `claude-haiku-4-5` | `gemini-2.0-flash` |

```python
# app/services/providers/google_provider.py
import asyncio
from collections.abc import AsyncGenerator
from fastapi import HTTPException
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from app.services.providers.base import BaseLLMProvider
from app.services.llm_helpers import parse_llm_response
from app.db.models.message import Message


def _to_google_contents(messages: list[dict]) -> list[dict]:
    """
    Convert shared message format (role: "user" | "assistant") to Google wire format.

    Google requires:
      - role: "user" | "model"  ("model" not "assistant")
      - content as parts list:  [{"text": "..."}]

    The shared build_messages() always produces role="assistant" for LLM turns.
    This function is the single translation point — nowhere else should care about
    Google's role naming.
    """
    result = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        result.append({
            "role": role,
            "parts": [{"text": m["content"]}],
        })
    return result


class GoogleProvider(BaseLLMProvider):

    async def stream_with_heartbeat(
        self, messages: list[dict], model: str, api_key: str
    ) -> AsyncGenerator[tuple[str, object], None]:
        from app.prompts.analysis_system import SYSTEM_PROMPT
        queue: asyncio.Queue = asyncio.Queue()
        full_text = ""
        google_contents = _to_google_contents(messages)

        async def llm_producer():
            nonlocal full_text
            try:
                client = genai.Client(api_key=api_key)
                stream = await client.aio.models.generate_content_stream(
                    model=model,
                    contents=google_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=4096,
                    ),
                )
                async for chunk in stream:
                    # chunk.text is None for non-text chunks (e.g. safety metadata)
                    text = chunk.text or ""
                    if text:
                        full_text += text
                        await queue.put(("token", text))
                await queue.put(("parsed", parse_llm_response(full_text)))
            except ClientError as e:
                status = getattr(e, "status_code", None)
                if status in (401, 403):
                    await queue.put(("error", "Invalid Google API key. Please update it in Settings."))
                elif status == 429:
                    await queue.put(("error", "Rate limit reached. Please wait a moment."))
                else:
                    await queue.put(("error", "A Google API error occurred. Please try again."))
            except ServerError:
                await queue.put(("error", "Google is overloaded. Please try again."))
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

    async def summarize_messages(self, messages: list[Message], api_key: str) -> str:
        client = genai.Client(api_key=api_key)
        content = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
        resp = await client.aio.models.generate_content(
            model="gemini-2.0-flash",   # cheapest fast model — mirrors claude-haiku-4-5 role
            contents=[{
                "role": "user",
                "parts": [{"text":
                    f"Summarize concisely. Preserve key decisions, insights, "
                    f"node modifications, open questions.\n\n{content}"
                }],
            }],
        )
        return resp.text

    async def validate_api_key(self, api_key: str) -> None:
        try:
            client = genai.Client(api_key=api_key)
            await client.aio.models.list()
        except ClientError as e:
            status = getattr(e, "status_code", None)
            if status in (401, 403):
                raise HTTPException(status_code=422, detail="Invalid Google API key")
            raise HTTPException(
                status_code=422,
                detail="Could not validate Google API key. Check your connection."
            )
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Could not validate Google API key. Check your connection."
            )
```

---

## 11. Updated `llm_service.py` — Thin Router

`llm_service.py` no longer contains any provider logic. It exposes the same public surface as before so every caller (`chat.py`, `session context management`) imports unchanged.

```python
# app/services/llm_service.py
"""
Public LLM surface — provider-agnostic.
All callers import from here. Provider is selected at runtime via LLM_PROVIDER env var.
"""
from app.config import get_settings
from app.services.providers.base import BaseLLMProvider
from app.db.models.message import Message
from app.schemas.graph import AnalysisGraph

# Re-export parse_llm_response so any existing import of it from llm_service still works
from app.services.llm_helpers import parse_llm_response as parse_llm_response  # noqa: F401


def get_provider(override: str | None = None) -> BaseLLMProvider:
    """
    Return the active provider instance.

    `override` is used only by the API key save route, which must validate
    against the provider the user is saving a key for — regardless of the
    server's currently active LLM_PROVIDER setting.
    """
    provider_name = (override or get_settings().LLM_PROVIDER).lower()
    if provider_name == "google":
        from app.services.providers.google_provider import GoogleProvider
        return GoogleProvider()
    from app.services.providers.anthropic_provider import AnthropicProvider
    return AnthropicProvider()


def build_messages(
    messages: list[Message],
    graph_state: AnalysisGraph,
    user_message: str,
    context_summary: str | None = None,
    context_summary_covers_up_to: int | None = None,
) -> list[dict]:
    """
    Builds the shared message list in Anthropic format (role: "user" | "assistant").
    Provider-agnostic. Each provider converts to its own wire format internally.
    This function is identical to the original in 06_BACKEND_IMPLEMENTATION.md §9.
    """
    settings = get_settings()
    result = []

    if context_summary and context_summary_covers_up_to is not None:
        result.append({"role": "user", "content": f"[Previous conversation summary]: {context_summary}"})
        result.append({"role": "assistant", "content": "Understood. Continuing from the summary."})
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


# Pass-through wrappers — callers use these directly, never get_provider() themselves
async def stream_with_heartbeat(messages: list[dict], model: str, api_key: str):
    async for event in get_provider().stream_with_heartbeat(messages, model, api_key):
        yield event


async def summarize_messages(messages: list[Message], api_key: str) -> str:
    return await get_provider().summarize_messages(messages, api_key)
```

---

## 12. Models Endpoint — Provider-Aware (`app/api/routes/models.py`)

`GET /api/models` must return the correct model list for the active provider.

```python
# app/api/routes/models.py
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter()

@router.get("/api/models")
async def list_models():
    settings = get_settings()
    return {
        "provider": settings.LLM_PROVIDER,
        "models": settings.ALLOWED_MODELS,
        "default": settings.DEFAULT_MODEL,
    }
```

The frontend model selector already reads from this endpoint — no frontend changes needed. It will automatically display Gemini models when the server switches to Google.

---

## 13. Session Model — `selected_model` Default

The `Session` model has a hardcoded default:

```python
# app/db/models/session.py
selected_model: Mapped[str] = mapped_column(String, default="claude-sonnet-4-6")
```

Change to read from settings at session creation time instead of hardcoding in the ORM default. In the `POST /api/sessions` route:

```python
# app/api/routes/sessions.py — POST /api/sessions
session = Session(
    user_id=current_user.id,
    idea=body.idea,
    name=body.idea[:60],
    selected_model=body.selected_model or get_settings().DEFAULT_MODEL,  # provider-aware default
    graph_state=build_initial_graph(body.idea),
)
```

Leave the column-level `default` as a fallback string (it does not affect runtime behaviour when the route sets the value explicitly).

---

## 14. Seed Script Changes (`app/db/seed.py`)

```python
# Replace the encrypted_api_key field:
user = User(
    email=SEED_EMAIL,
    name="Test User",
    password_hash=hash_password(SEED_PASSWORD),
    encrypted_anthropic_api_key=(
        encrypt_api_key(settings.SEED_ANTHROPIC_API_KEY)
        if settings.SEED_ANTHROPIC_API_KEY else None
    ),
    encrypted_google_api_key=(
        encrypt_api_key(settings.SEED_GOOGLE_API_KEY)
        if settings.SEED_GOOGLE_API_KEY else None
    ),
)

# Replace hardcoded model in the seeded Session:
db.add(Session(
    user_id=user.id,
    name="Restaurant Inventory SaaS",
    idea=SEED_IDEA,
    graph_state=SEED_GRAPH,
    selected_model=settings.DEFAULT_MODEL,   # provider-aware
))

# Update the final print:
if not settings.SEED_ANTHROPIC_API_KEY and not settings.SEED_GOOGLE_API_KEY:
    print("  ⚠ No SEED_*_API_KEY set — user has no API key (must set in /settings)")
```

---

## 15. Test Fixtures (`tests/conftest.py`)

### 15a. Updated `mock_anthropic`

The column rename from `encrypted_api_key` → `encrypted_anthropic_api_key` does not affect the `mock_anthropic` fixture itself (it patches the SDK, not the DB). However, any test that sets an API key on a user directly must use the new column name:

```python
# BEFORE (old column — remove these):
user.encrypted_api_key = encrypt_api_key("sk-ant-...")

# AFTER (new column):
user.encrypted_anthropic_api_key = encrypt_api_key("sk-ant-...")
```

The `mock_anthropic` fixture body from `06_BACKEND_IMPLEMENTATION.md §13` is otherwise **unchanged** — copy it verbatim. No modifications to the fixture class structure are required.

### 15b. New `mock_google` fixture

```python
# Add to tests/conftest.py

@pytest.fixture
def mock_google(monkeypatch):
    """Patches google-genai SDK — no real API calls in tests."""
    FAKE_RESPONSE = (
        '<GRAPH_ACTIONS>[{"action":"add","payload":{"id":"n1","type":"concept",'
        '"label":"Test","content":"Content","score":null,"parent_id":null}}]</GRAPH_ACTIONS>'
        '\nHere is my analysis.'
    )

    class FakeChunk:
        text = FAKE_RESPONSE

    class FakeStream:
        """Async iterable — mirrors what client.aio.models.generate_content_stream() returns."""
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            yield FakeChunk()

    class FakeModels:
        async def generate_content_stream(self, **kwargs) -> "FakeStream":
            # The Google provider does: stream = await client.aio.models.generate_content_stream(...)
            # then: async for chunk in stream — so this must be a coroutine returning an async iterable.
            return FakeStream()

        async def list(self):
            return []

        async def generate_content(self, **kwargs):
            class R:
                text = "Summary text."
            return R()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        aio = FakeAio()

    import google.genai as genai_module
    monkeypatch.setattr(genai_module, "Client", lambda **kw: FakeClient())
    return FakeClient()
```

### 15c. Setting `LLM_PROVIDER` in tests

Tests for the Google path must override `LLM_PROVIDER` so the router in `llm_service.get_provider()` picks `GoogleProvider`. Do this inside the test using `monkeypatch` on the cached settings object:

```python
async def test_chat_google(authed_client, mock_google, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "LLM_PROVIDER", "google")
    # ... rest of test unchanged
```

Tests for the Anthropic path (the default) require no change — `LLM_PROVIDER` defaults to `"anthropic"`.

---

## 16. Operational Notes

**Switching providers in production:**
1. Update `LLM_PROVIDER` in the environment (EC2 `.env` / Railway variable)
2. Redeploy — no code change, no migration needed (both key columns always exist)
3. Users who have only one provider's key set will get an "API key not set" SSE error on their next request — prompt them to add the key in Settings

**Both providers can coexist in the same deployment:** A user can have both keys saved. If you later add per-user provider selection (V2 scope), the DB schema is already ready — just expose a `preferred_provider` column on `User` and route accordingly in the chat endpoint.

**Safety filters (Google-specific):** Google's API applies safety filters that can block responses Anthropic would allow. If the LLM returns an empty `chunk.text` stream with no tokens, check `chunk.prompt_feedback` for `BLOCK_REASON`. The current implementation treats this as an empty response (no error event). If this becomes a user-facing problem, add a check after the stream loop: if `full_text` is empty and no error was queued, yield `("error", "Response was blocked by Google's safety filters.")`.

**Context window:** `CONTEXT_WINDOW_MAX_MESSAGES=20` applies identically to both providers. The summarization model differs (`haiku` vs `gemini-2.0-flash`) but the summarization logic and storage are unchanged.