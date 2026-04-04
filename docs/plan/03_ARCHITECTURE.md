# ARCHITECTURE PLAN — IdeaLens
> Stack: React + Vite (apps/web-react) · SvelteKit (apps/web-svelte) · Python + FastAPI (apps/api) · Pydantic v2 · Anthropic SDK (user key) · PostgreSQL + SQLAlchemy 2.x async + Alembic · Terraform + AWS
>
> Two frontend implementations share one backend, one database, and one infrastructure.
> Only one frontend is deployed to production at a time — selected via DEPLOY_FRONTEND=react|svelte.
> Frontend A (React): 07_FRONTEND_IMPLEMENTATION.md
> Frontend B (SvelteKit): 07_FRONTEND_IMPLEMENTATION_SVELTE.md

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PUBLIC INTERNET                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                    ┌────────▼────────┐
                    │  AWS ALB        │
                    │  TLS via ACM    │
                    │  idle timeout 60s│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │ /*                          │ /api/*, /auth/*
     ┌────────▼────────┐         ┌──────────▼──────────┐
     │   Web Frontend  │         │    API Backend       │
     │  react OR svelte│         │  Python + FastAPI    │
     │  (one at a time)│         │  uvicorn             │
     │  ECS 256/512    │         │  ECS 512/1024        │
     └─────────────────┘         └──────────┬───────────┘
                                            │
                         ┌──────────────────┼──────────┐
                         │                             │
              ┌───────────▼──────┐         ┌───────────▼──────────┐
              │   RDS PostgreSQL │         │  Anthropic API       │
              │   db.t3.micro    │         │  key per-user,       │
              │   sg-rds only    │         │  encrypted at rest   │
              └──────────────────┘         └──────────────────────┘

AWS Secrets Manager: JWT_SECRET, API_KEY_ENCRYPTION_KEY, DATABASE_URL
Terraform: all AWS resources (state in S3 + DynamoDB lock)
GitHub Actions: CI on PR (3 parallel jobs); build + deploy on push to main
  → DEPLOY_FRONTEND secret (react|svelte) controls which frontend image is deployed
```

**Production:** One `web` ECS service runs whichever frontend image was last deployed.
Switching frontends means changing `DEPLOY_FRONTEND` and re-running the deploy workflow —
no Terraform changes required, just an ECS service update with the new image URI.

**Local development:** Both frontends run simultaneously against one API container.
- React frontend: http://localhost:3000
- SvelteKit frontend: http://localhost:3001
- API: http://localhost:8000 (with /docs available in development)

---

## 2. Networking — AWS Default VPC + Security Groups

```
sg-alb: inbound 443+80 from 0.0.0.0/0; outbound to sg-web, sg-api
sg-web: inbound TCP 80 from sg-alb; outbound all (ECR pull, Secrets Manager)
sg-api: inbound TCP 8000 from sg-alb; outbound all + TCP 5432 to sg-rds
sg-rds: inbound TCP 5432 from sg-api ONLY; no outbound
```

A single `sg-web` covers whichever frontend is deployed. Both frontend containers expose
port 80 in production — the React container via nginx, the SvelteKit container via its
Node server configured with `PORT=80`. Security groups therefore require no changes when
switching frontends. RDS is unreachable from the internet; only api tasks reach it via sg-rds.

---

## 3. Repository Structure

```
idealens/
├── apps/
│   ├── web-react/                      # Frontend A — React + Vite
│   │   ├── src/
│   │   │   ├── main.tsx                # QueryClientProvider + BrowserRouter
│   │   │   ├── App.tsx                 # Route tree
│   │   │   ├── config.ts               # API_BASE_URL from VITE_API_URL
│   │   │   ├── pages/
│   │   │   │   ├── Login.tsx
│   │   │   │   ├── Register.tsx
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Session.tsx
│   │   │   │   ├── Settings.tsx
│   │   │   │   └── NotFound.tsx
│   │   │   ├── components/
│   │   │   │   ├── auth/
│   │   │   │   │   ├── ProtectedRoute.tsx
│   │   │   │   │   └── ApiKeyGuard.tsx
│   │   │   │   ├── chat/
│   │   │   │   │   ├── ChatPanel.tsx
│   │   │   │   │   ├── MessageBubble.tsx
│   │   │   │   │   ├── ChatInput.tsx
│   │   │   │   │   └── ModelSelector.tsx
│   │   │   │   ├── graph/
│   │   │   │   │   ├── GraphPanel.tsx
│   │   │   │   │   ├── GraphToolbar.tsx
│   │   │   │   │   ├── NodeDetailPanel.tsx
│   │   │   │   │   ├── AddNodeModal.tsx
│   │   │   │   │   └── nodes/
│   │   │   │   │       └── AnalysisNodeComponent.tsx
│   │   │   │   ├── layout/
│   │   │   │   │   ├── AppHeader.tsx
│   │   │   │   │   └── SplitLayout.tsx
│   │   │   │   └── session/
│   │   │   │       └── NewAnalysisModal.tsx
│   │   │   ├── stores/
│   │   │   │   ├── authStore.ts        # Zustand, persisted
│   │   │   │   ├── chatStore.ts        # Zustand
│   │   │   │   ├── graphStore.ts       # Zustand + immer
│   │   │   │   └── sessionStore.ts     # Zustand
│   │   │   ├── services/
│   │   │   │   ├── api.ts              # Axios + interceptors
│   │   │   │   ├── authService.ts
│   │   │   │   ├── userService.ts
│   │   │   │   ├── sessionService.ts
│   │   │   │   └── chatService.ts      # SSE fetch stream
│   │   │   ├── schemas/
│   │   │   │   └── graph.ts            # Zod schemas
│   │   │   └── utils/
│   │   │       ├── graphLayout.ts      # Dagre layout
│   │   │       ├── graphStyles.ts      # colour/icon map
│   │   │       ├── graphGuards.ts
│   │   │       └── debounce.ts
│   │   ├── .env.development            # VITE_API_URL=http://localhost:8000
│   │   ├── .env.production             # VITE_API_URL= (empty — same-origin via nginx)
│   │   ├── index.html
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── tailwind.config.ts
│   │   ├── nginx.conf                  # serves static files + proxies /api/ /auth/
│   │   ├── README.md
│   │   └── Dockerfile                  # dev + production (nginx) stages
│   │
│   ├── web-svelte/                     # Frontend B — SvelteKit
│   │   ├── src/
│   │   │   ├── app.css
│   │   │   ├── app.d.ts
│   │   │   ├── lib/
│   │   │   │   ├── config.ts           # API_BASE_URL from PUBLIC_API_URL
│   │   │   │   ├── schemas/
│   │   │   │   │   └── graph.ts        # Zod schemas (identical content to React version)
│   │   │   │   ├── stores/
│   │   │   │   │   ├── authStore.ts    # Svelte writable + localStorage
│   │   │   │   │   ├── chatStore.ts    # Svelte writable
│   │   │   │   │   ├── graphStore.ts   # Svelte writable
│   │   │   │   │   └── sessionStore.ts # Svelte writable
│   │   │   │   ├── services/
│   │   │   │   │   ├── api.ts          # Axios + interceptors (same logic as React)
│   │   │   │   │   ├── authService.ts
│   │   │   │   │   ├── userService.ts
│   │   │   │   │   ├── sessionService.ts
│   │   │   │   │   └── chatService.ts  # SSE fetch stream (same logic as React)
│   │   │   │   ├── components/
│   │   │   │   │   ├── chat/
│   │   │   │   │   │   ├── ChatPanel.svelte
│   │   │   │   │   │   ├── MessageBubble.svelte
│   │   │   │   │   │   ├── ChatInput.svelte
│   │   │   │   │   │   └── ModelSelector.svelte
│   │   │   │   │   ├── graph/
│   │   │   │   │   │   ├── GraphPanel.svelte
│   │   │   │   │   │   ├── GraphToolbar.svelte
│   │   │   │   │   │   ├── NodeDetailPanel.svelte
│   │   │   │   │   │   ├── AddNodeModal.svelte
│   │   │   │   │   │   └── nodes/
│   │   │   │   │   │       └── AnalysisNodeComponent.svelte
│   │   │   │   │   ├── layout/
│   │   │   │   │   │   ├── AppHeader.svelte
│   │   │   │   │   │   └── SplitLayout.svelte
│   │   │   │   │   └── session/
│   │   │   │   │       └── NewAnalysisModal.svelte
│   │   │   │   └── utils/
│   │   │   │       ├── graphLayout.ts  # Dagre layout (identical content to React version)
│   │   │   │       ├── graphStyles.ts  # colour/icon map (identical content)
│   │   │   │       ├── graphGuards.ts  # (identical content)
│   │   │   │       └── debounce.ts     # (identical content)
│   │   │   └── routes/
│   │   │       ├── +layout.ts          # ssr = false (SPA mode)
│   │   │       ├── +layout.svelte      # Toaster, auth init
│   │   │       ├── login/
│   │   │       │   └── +page.svelte
│   │   │       ├── register/
│   │   │       │   └── +page.svelte
│   │   │       └── (protected)/
│   │   │           ├── +layout.ts      # auth guard → redirect /login
│   │   │           ├── settings/
│   │   │           │   └── +page.svelte
│   │   │           └── (requires-api-key)/
│   │   │               ├── +layout.ts  # api key guard → redirect /settings
│   │   │               ├── +page.svelte # Dashboard
│   │   │               └── session/
│   │   │                   └── [id]/
│   │   │                       └── +page.svelte
│   │   ├── static/
│   │   ├── .env.development            # PUBLIC_API_URL=http://localhost:8000
│   │   ├── .env.production             # PUBLIC_API_URL= (empty — same-origin via ALB)
│   │   ├── svelte.config.js
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── tailwind.config.ts
│   │   ├── README.md
│   │   └── Dockerfile                  # dev + production (Node/adapter-node) stages
│   │
│   └── api/                            # Backend — shared by both frontends
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── dependencies/
│       │   │   └── auth.py
│       │   ├── api/routes/
│       │   │   ├── auth.py
│       │   │   ├── users.py
│       │   │   ├── sessions.py
│       │   │   ├── chat.py
│       │   │   └── models.py
│       │   ├── services/
│       │   │   ├── auth_service.py
│       │   │   ├── llm_service.py
│       │   │   ├── encryption_service.py
│       │   │   └── email_service.py    # stub — v2
│       │   ├── db/
│       │   │   ├── base.py
│       │   │   ├── session.py
│       │   │   ├── seed.py
│       │   │   └── models/
│       │   │       ├── __init__.py
│       │   │       ├── base.py
│       │   │       ├── user.py
│       │   │       ├── refresh_token.py
│       │   │       ├── session.py
│       │   │       └── message.py
│       │   ├── schemas/
│       │   │   ├── auth.py
│       │   │   ├── user.py
│       │   │   ├── session.py
│       │   │   ├── chat.py
│       │   │   ├── graph.py
│       │   │   └── models.py
│       │   └── prompts/
│       │       ├── analysis_system.py
│       │       └── README.md
│       ├── alembic/
│       │   ├── env.py
│       │   └── versions/
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── test_auth.py
│       │   ├── test_users.py
│       │   ├── test_sessions.py
│       │   ├── test_chat.py
│       │   └── test_llm_service.py
│       ├── pyproject.toml
│       ├── alembic.ini
│       └── Dockerfile
│
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── terraform.tfvars
│   ├── terraform.tfvars.example
│   ├── outputs.tf
│   ├── backend.tf
│   ├── modules/
│   │   ├── networking/
│   │   ├── ecr/                        # 3 repos: idealens-api, idealens-web-react, idealens-web-svelte
│   │   ├── rds/
│   │   ├── secrets/
│   │   ├── iam/
│   │   ├── alb/
│   │   ├── acm/
│   │   └── ecs/                        # cluster, 2 services (api + web), migrate task
│   │                                   # web service image URI set at deploy time via DEPLOY_FRONTEND
│   └── README.md
│
├── docker-compose.yml                  # all 4 services for local dev: postgres, api, web-react, web-svelte
├── .github/workflows/
│   ├── ci.yml                          # 3 parallel jobs: backend, frontend-react, frontend-svelte
│   └── deploy.yml                      # builds api + selected frontend; DEPLOY_FRONTEND=react|svelte
└── README.md
```

---

## 4. Database Schema


*Shared by both frontends.*

```sql
CREATE TABLE users (
    id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email             TEXT UNIQUE NOT NULL,
    name              TEXT NOT NULL,
    password_hash     TEXT NOT NULL,
    encrypted_api_key TEXT,           -- NULL = not set
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()   -- SQLAlchemy onupdate=func.now()
);

CREATE TABLE refresh_tokens (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    token      TEXT UNIQUE NOT NULL,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    id                           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id                      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                         TEXT NOT NULL DEFAULT 'Untitled Analysis',
    idea                         TEXT NOT NULL,
    graph_state                  JSONB NOT NULL DEFAULT '{"nodes":[],"edges":[]}',
    selected_model               TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
    context_summary              TEXT,           -- NULL until first compression
    context_summary_covers_up_to INT,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()  -- onupdate=func.now()
);

CREATE TABLE messages (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content       TEXT NOT NULL,
    message_index INT NOT NULL,      -- assigned via SELECT FOR UPDATE to prevent race conditions
    metadata      JSONB,             -- stores graph_actions for SSE replay
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_user_updated ON sessions(user_id, updated_at DESC);
CREATE INDEX idx_messages_session_idx  ON messages(session_id, message_index ASC);
CREATE UNIQUE INDEX idx_messages_unique_idx ON messages(session_id, message_index);
CREATE INDEX idx_refresh_token_user    ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_token_token   ON refresh_tokens(token);
```

---

## 5. API Endpoints

*Shared by both frontends.*

### Auth (`/auth`)
```
POST /auth/register   { email, name, password }        → TokenResponse + Set-Cookie: refresh_token
POST /auth/login      { email, password }               → TokenResponse + Set-Cookie: refresh_token
POST /auth/refresh    Cookie: refresh_token             → TokenResponse
POST /auth/logout     Cookie: refresh_token             → 204
```
Cookie spec: `httponly=True, samesite="strict", path="/auth", max_age=604800, secure=True (prod only)`

### Users (`/api/users`) — Bearer required
```
GET    /api/users/me                 → UserResponse { id, email, name, has_api_key: bool }
PATCH  /api/users/me                 { name }                    → UserResponse
POST   /api/users/me/password        { current_password, new_password } → 204
POST   /api/users/me/api-key         { api_key }                 → UserResponse (validates live)
DELETE /api/users/me/api-key                                     → UserResponse
DELETE /api/users/me                 { password }                → 204 (cascade all data)
```

### Models (`/api/models`) — public
```
GET /api/models  → [{ id, display_name, description }]
```

### Sessions (`/api/sessions`) — Bearer required
```
GET    /api/sessions?page=1&limit=20  → { items: SessionListItem[], total: int, page: int }
POST   /api/sessions                  { idea, selected_model } → SessionResponse (with root node)
GET    /api/sessions/{id}             → SessionResponse + messages[] + graph_state
PATCH  /api/sessions/{id}             { name?, selected_model? } → SessionResponse
DELETE /api/sessions/{id}             → 204
PUT    /api/sessions/{id}/graph       { graph_state: AnalysisGraph } → 204
```
All session routes return 403 (not 404) when session exists but belongs to another user.

### Chat (`/api/chat`) — Bearer required
```
POST /api/chat  { session_id, message, graph_state, model }
                Header: Last-Event-ID (optional, for reconnection)
                → text/event-stream

SSE events (in order):
  event: ping         data:                  (every 15s, keep-alive)
  event: token        data: "text chunk"     (streamed as LLM generates)
  event: graph_action data: { action, payload } (after stream completes, one per action)
  event: error        data: "message"        (on any failure)
  event: done         data: [DONE]           (always last)

Every event has: id: <message_uuid>
Headers: Cache-Control: no-cache, X-Accel-Buffering: no
```

### System
```
GET /health  → { status: "ok", environment: str }
GET /docs    → OpenAPI UI (development only; None in production)
```

---

## 6. Pydantic Schema Design

The key design decision — `AddNodeAction` uses `NodePayload` (no position),
not `AnalysisNode` — applies to both frontends identically. The Zod mirror schemas in
both frontends are identical in content; only the file path differs:

| | React | SvelteKit |
|---|---|---|
| Zod schemas | `apps/web-react/src/schemas/graph.ts` | `apps/web-svelte/src/lib/schemas/graph.ts` |
| Content | Identical | Identical |

---

## 7. Zod Mirror Schemas (both frontends)

The Zod schema content is identical between both frontends. The full schema is defined in
07_FRONTEND_IMPLEMENTATION.md §8 (React) and 07_FRONTEND_IMPLEMENTATION_SVELTE.md §9
(SvelteKit). Both files contain identical type definitions.

---

## 8. LLM Streaming Flow

Both frontends implement the same SSE client logic
using the `fetch`-based `chatService.ts`. The logic is identical; only import paths differ.

```
User submits (isStreaming locked)
    │
    │  POST /api/chat  { session_id, message, graph_state, model }
    ▼
FastAPI chat route
    ├── Pydantic validates (model allowlist + graph size ≤200/400)
    ├── get_current_user → verify JWT
    ├── Load session → 403 if not owner
    ├── Decrypt API key → SSE error if not set
    ├── Check Last-Event-ID → replay if found in DB
    ├── Context check → summarize if needed
    └── Build messages array
            │
            ▼
    asyncio.Queue consumed by SSE generator:
    ├── LLM producer: anthropic.messages.stream() → push (token, chunk) to queue
    ├── Ping producer: every 15s → push (ping, None) to queue
    └── SSE generator: reads queue
            ├── ping  → yield "event: ping\ndata: \n\n"
            ├── token → yield "id: {uuid}\nevent: token\ndata: {chunk}\n\n"
            └── done  → parse full text → validate graph actions → yield graph_action events
                                                                  → yield done
                                                                  → persist messages (FOR UPDATE)

Client receives SSE:
    ├── token        → chatStore.appendToken()
    ├── graph_action → Zod validate → graphStore.applyGraphActions()
    ├── error        → chatStore.setError()
    └── done         → chatStore.finalizeMessage() → isStreaming = false
```

---

## 9. Graph Flow — Controlled Pattern

Both frontends follow the same controlled pattern: the graph store is the single source
of truth; the flow library renders from it. `nodeTypes` must be at module level in both.

| Concern | React (web-react) | SvelteKit (web-svelte) |
|---|---|---|
| Library | `@xyflow/react` | `@xyflow/svelte` |
| Store | Zustand (`useGraphStore`) | Svelte writable (`graphStore`) |
| Nodes derived | `.map()` in render | `derived()` store |
| Node types registered | Module-level `const nodeTypes` | Module-level `const nodeTypes` |
| Drag stop | `onNodeDragStop` prop | `on:nodedragstop` event |
| Delete | `onNodesDelete` prop | `on:nodesdelete` event |

See 07_FRONTEND_IMPLEMENTATION.md §9 (React) and 07_FRONTEND_IMPLEMENTATION_SVELTE.md §11 (SvelteKit).

---

## 10. Frontend State Architecture

Both frontends maintain the same four stores with the same shape and method names.
The implementation mechanism differs (Zustand vs Svelte writable) but the interface is
deliberately kept parallel to make comparison straightforward.

```
authStore:
  state:   { user: User | null, accessToken: string | null }
  methods: setUser / setAccessToken / updateUser / logout
  persist: localStorage (Zustand middleware in React; manual in SvelteKit)

chatStore:
  state:   { messages: ChatMessage[], isStreaming: bool, error: string | null }
  methods: addMessage / appendToken / finalizeMessage / setError / setStreaming / setMessages / clear

graphStore:
  state:   { nodes: AnalysisNode[], edges: AnalysisEdge[], selectedNodeId: string | null }
  methods: setGraph / applyGraphActions / addNode / updateNode / deleteNode
           addEdge / deleteEdge / setNodePosition / setSelectedNodeId / clearGraph

sessionStore:
  state:   { sessions, currentSessionId, currentSession, selectedModel, isLoading, error }
  methods: fetchSessions / createSession / loadSession / saveGraph(debounced 1s)
           updateSession / deleteSession / setSelectedModel
```

| | React | SvelteKit |
|---|---|---|
| Store primitive | `zustand` + `immer` (graphStore) | `svelte/store` writable |
| Subscribe | `useGraphStore(s => s.nodes)` | `$graphStore.nodes` |
| Read outside reactive | `useStore.getState()` | `get(store)` |
| Persist auth | `zustand/middleware/persist` | `localStorage` in store methods |

---

## 11. Alembic Async Configuration

Standard Alembic does not work with async SQLAlchemy. `alembic/env.py` must use the async pattern:

```python
# alembic/env.py — key sections
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.db.models.base import Base
import app.db.models  # noqa — registers all models via __init__.py

def run_migrations_offline() -> None:
    url = get_settings().DATABASE_URL
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    engine = create_async_engine(get_settings().DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

`alembic.ini` — set `sqlalchemy.url` to a placeholder (overridden in env.py):
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://placeholder
```

---

## 12. Security Architecture

| Layer | Mechanism |
|---|---|
| Transport | HTTPS enforced; HSTS in production |
| CORS | Both frontend origins allowed in development; only the deployed frontend's origin in production |
| Auth | JWT HS256; 15-min access token; 7-day refresh in httpOnly cookie path=/auth |
| API Key | Fernet-encrypted at rest; `has_api_key: bool` only exposed to frontend |
| API Key Validation | Live Anthropic test call on save; invalid → 422 before storing |
| Secrets | AWS Secrets Manager → ECS env vars; never in image or logs |
| DB | sg-rds accepts port 5432 from sg-api only |
| Input | Pydantic v2 all requests; Zod all forms |
| Graph size | ≤200 nodes / ≤400 edges — Pydantic field_validator |
| Model | ALLOWED_MODELS allowlist in Pydantic field_validator |
| Rate limiting | slowapi: /auth 5/15min IP; /api/chat 30/min user; /api/sessions 60/min user |
| CORS | FRONTEND_URL only; allow_credentials=True |
| Headers | X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS (prod) |
| Middleware order | SecurityHeaders → CORS → routes (CORS must be inner to handle OPTIONS) |
| Session ownership | 403 (not 404) when resource exists but belongs to another user |
| Message index | SELECT FOR UPDATE prevents concurrent index collision |
| Concurrent send | isStreaming guard blocks second message at UI level |
| Account delete | Password confirmation + cascade |

CORS `allow_origins` in development includes both:
```python
allow_origins=["http://localhost:3000", "http://localhost:3001"]
```
In production, set to only the single deployed frontend origin.

---

## 13. Terraform Resource Sizes

```hcl
# infra/terraform.tfvars
aws_region = "us-east-1"

# ECS task sizes
api_task_cpu    = 512     # 0.5 vCPU
api_task_memory = 1024    # 1 GB
web_task_cpu    = 256     # 0.25 vCPU — same var regardless of which frontend is deployed
web_task_memory = 512     # 512 MB
ecs_desired_count = 1

# RDS
rds_instance_class    = "db.t3.micro"
rds_allocated_storage = 20
rds_engine_version    = "16"

# ALB — must be >= SSE heartbeat interval (15s) + comfortable buffer
alb_idle_timeout = 60

# Domain (update when domain is acquired)
domain_name = ""
```

Estimated v1 cost: ~$57/month — identical to the single-frontend original, since only
one web ECS service runs in production regardless of which frontend is selected.
Anthropic API costs are fully user-paid.