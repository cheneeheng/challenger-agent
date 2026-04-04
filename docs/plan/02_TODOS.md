# TODOS — IdeaLens
> Stack: React + Vite (apps/web-react) · SvelteKit (apps/web-svelte) · Python + FastAPI (apps/api, shared)
> Pydantic v2 · Anthropic SDK (user key) · PostgreSQL + SQLAlchemy 2.x async + Alembic · Terraform + AWS
>
> Frontend implementation details:
>   React version    → 07_FRONTEND_IMPLEMENTATION.md
>   SvelteKit version → 07_FRONTEND_IMPLEMENTATION_SVELTE.md
> Backend implementation details: see 06_BACKEND_IMPLEMENTATION.md, 08_LLM_AND_PROMPT.md
> Infrastructure details: see 05_INFRASTRUCTURE_AND_DEPLOYMENT.md
>
> Notation: tasks marked [React] or [Svelte] are frontend-specific.
> Tasks with no tag apply to both frontends or to the shared backend/infra.

---

## PHASE 1 — Foundation

### 1.1 Project Scaffolding
- [ ] Create root monorepo structure:
  ```
  idealens/
  ├── apps/
  │   ├── api/          # Python + FastAPI backend (shared)
  │   ├── web-react/    # React + Vite frontend
  │   └── web-svelte/   # SvelteKit frontend
  ├── infra/
  └── docker-compose.yml
  ```
- [ ] Create root `.gitignore`: `node_modules/`, `__pycache__/`, `*.pyc`, `.env`, `dist/`, `.venv/`, `.terraform/`, `*.tfstate`, `*.tfstate.backup`, `.terraform.lock.hcl`, `.svelte-kit/`
- [ ] Initialize Git repository at monorepo root
- [ ] Create `/apps/api/.env.example` (see §1.4 for full contents)
- [ ] [React] Create `/apps/web-react/.env.example` (`VITE_API_URL=http://localhost:8000`)
- [ ] [Svelte] Create `/apps/web-svelte/.env.example` (`PUBLIC_API_URL=http://localhost:8000`)

### 1.2 docker-compose.yml
Both frontends are available in local dev simultaneously — React on port 3000, SvelteKit on
port 3001. Both talk to the same API container. Use `docker-compose up` to run everything,
or pass service names to run only one frontend (see §11 in 05_INFRASTRUCTURE_AND_DEPLOYMENT.md).
The postgres healthcheck prevents api starting before DB is ready.

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: idealens
      POSTGRES_PASSWORD: idealens
      POSTGRES_DB: idealens
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U idealens"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ./apps/api
      target: development
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./apps/api:/app
      - /app/.venv
    ports: ["8000:8000"]
    env_file: ./apps/api/.env
    depends_on:
      postgres:
        condition: service_healthy

  web-react:
    build:
      context: ./apps/web-react
      target: development
    command: npm run dev -- --host 0.0.0.0 --port 3000
    volumes:
      - ./apps/web-react:/app
      - /app/node_modules
    ports: ["3000:3000"]
    environment:
      VITE_API_URL: http://localhost:8000

  web-svelte:
    build:
      context: ./apps/web-svelte
      target: development
    command: npm run dev -- --host 0.0.0.0 --port 3001
    volumes:
      - ./apps/web-svelte:/app
      - /app/node_modules
    ports: ["3001:3001"]
    environment:
      PUBLIC_API_URL: http://localhost:8000

volumes:
  postgres_data:
```

- [ ] Create `apps/api/Dockerfile` with `development` and `production` stages (see §5.6)
- [ ] [React] Create `apps/web-react/Dockerfile` with `development` and `production` stages (see §5.6)
- [ ] [Svelte] Create `apps/web-svelte/Dockerfile` with `development` and `production` stages (see §5.6)

### 1.3 Environment Variables

**[React] `apps/web-react`:**
- [ ] Create `apps/web-react/.env.development`: `VITE_API_URL=http://localhost:8000`
- [ ] Create `apps/web-react/.env.production`: `VITE_API_URL=` (intentionally empty — same-origin via nginx)
- [ ] Create `apps/web-react/src/config.ts`:
  ```typescript
  export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
  ```
- [ ] Configure `apps/web-react/vite.config.ts`:
  ```typescript
  import { defineConfig } from 'vite'
  import react from '@vitejs/plugin-react'
  import tailwindcss from '@tailwindcss/vite'

  export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      port: 3000,
      hmr: { host: 'localhost', port: 3000 },
    },
  })
  ```

**[Svelte] `apps/web-svelte`:**
- [ ] Create `apps/web-svelte/.env.development`: `PUBLIC_API_URL=http://localhost:8000`
- [ ] Create `apps/web-svelte/.env.production`: `PUBLIC_API_URL=` (intentionally empty)
- [ ] Create `apps/web-svelte/src/lib/config.ts`:
  ```typescript
  import { PUBLIC_API_URL } from '$env/static/public'
  export const API_BASE_URL: string = PUBLIC_API_URL ?? ''
  ```
- [ ] Configure `apps/web-svelte/vite.config.ts` (via `svelte.config.js` + vite plugin — see 07_FRONTEND_IMPLEMENTATION_SVELTE.md §1)
- [ ] Create `apps/web-svelte/src/routes/+layout.ts` with `export const ssr = false` (SPA mode)

### 1.4 Backend Base Setup
- [ ] `cd apps/api && uv init && uv venv`
- [ ] Install dependencies:
  ```
  uv add fastapi uvicorn[standard] pydantic[email] pydantic-settings structlog \
         sqlalchemy[asyncio] asyncpg alembic \
         python-jose[cryptography] passlib[bcrypt] python-multipart \
         cryptography anthropic slowapi
  uv add --dev pytest pytest-asyncio httpx ruff mypy
  ```
- [ ] Run `uv lock` to generate the lockfile (required for `uv sync --frozen` in production Docker builds)
- [ ] Configure `pyproject.toml`:
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
- [ ] Create `app/config.py` — pydantic-settings `Settings` with `get_settings()` lru_cache singleton (see 06_BACKEND_IMPLEMENTATION.md §2 for full class)
- [ ] Create `app/main.py` — `create_app()` factory; middleware order is critical:
  1. `SecurityHeadersMiddleware` added first (outermost)
  2. `CORSMiddleware` added second — must be before security headers or OPTIONS preflight fails; `allow_origins` reads from `settings.FRONTEND_URLS` (a list — see 06_BACKEND_IMPLEMENTATION.md §2); default covers both dev frontends (`http://localhost:3000` and `http://localhost:3001`)
  3. `slowapi` limiter added to `app.state`
  4. Routers included last
- [ ] Add `GET /health` endpoint
- [ ] Configure `structlog`: JSON in production, human-readable ConsoleRenderer in development

### 1.5 Database Setup — SQLAlchemy + Alembic Async
- [ ] Create `app/db/models/__init__.py` — **import all models here** so Alembic autogenerate can discover them:
  ```python
  from app.db.models.user import User          # noqa: F401
  from app.db.models.refresh_token import RefreshToken  # noqa: F401
  from app.db.models.session import Session    # noqa: F401
  from app.db.models.message import Message    # noqa: F401
  ```
- [ ] Create `app/db/models/base.py`:
  ```python
  from sqlalchemy.orm import DeclarativeBase
  class Base(DeclarativeBase):
      pass
  ```
- [ ] Create all four models with correct `onupdate=func.now()` on `updated_at` (see 06_BACKEND_IMPLEMENTATION.md §3)
- [ ] Create `app/db/base.py` — async engine + `AsyncSessionLocal`
- [ ] Create `app/db/session.py` — `get_db` async generator dependency with commit/rollback
- [ ] Initialize Alembic: `alembic init alembic/`
- [ ] Configure `alembic/env.py` for async — **this is non-trivial, use exact pattern from 06_BACKEND_IMPLEMENTATION.md §5**:
  - Override `sqlalchemy.url` from `get_settings().DATABASE_URL`
  - Import `Base` from `app.db.models.base`
  - Import `app.db.models` (the `__init__.py`) to register all models
  - Use `run_async_migrations()` with `AsyncEngine` and `conn.run_sync(do_run_migrations)`
- [ ] Set `sqlalchemy.url` in `alembic.ini` to a placeholder (real URL comes from `env.py`):
  ```ini
  sqlalchemy.url = postgresql+asyncpg://placeholder
  ```
- [ ] Generate and apply initial migration:
  ```bash
  alembic revision --autogenerate -m "initial_schema"
  alembic upgrade head
  ```
- [ ] Create `app/db/seed.py` — idempotent seed script (see 06_BACKEND_IMPLEMENTATION.md §11)

### 1.6 API Key Encryption Service
- [ ] Create `app/services/encryption_service.py` using `cryptography.fernet.Fernet`
- [ ] Add `API_KEY_ENCRYPTION_KEY` to `.env.example` with generation command
- [ ] Document: key is never returned in any API response; decrypted only in-memory during LLM calls

### 1.7 Authentication — Backend
- [ ] Create `app/schemas/auth.py` — `RegisterRequest`, `LoginRequest`, `TokenResponse`, `UserResponse` (with `has_api_key: bool`)
- [ ] Create `app/services/auth_service.py` — hash, verify, create/verify JWT tokens
- [ ] Create `app/api/routes/auth.py`:
  - `POST /auth/register` → hash password, insert user, set tokens
  - `POST /auth/login` → verify, set tokens
  - `POST /auth/refresh` → read httpOnly cookie, return new access token
  - `POST /auth/logout` → clear cookie, delete refresh token record
- [ ] **Refresh token cookie spec** — must be set identically in register AND login:
  ```python
  response.set_cookie(
      key="refresh_token",
      value=refresh_token,
      httponly=True,
      secure=settings.ENVIRONMENT == "production",  # False in dev (no HTTPS locally)
      samesite="strict",
      max_age=60 * 60 * 24 * 7,   # 7 days in seconds
      path="/auth",                 # cookie only sent to /auth/* routes
  )
  ```
- [ ] Create `app/dependencies/auth.py` — `get_current_user` dependency
- [ ] Write pytest tests: register, login, refresh, logout, protected route access

### 1.8 User Settings — Backend
- [ ] Create `app/schemas/user.py` — `UpdateProfileRequest`, `ChangePasswordRequest`, `SetApiKeyRequest` (validates `sk-ant-` prefix), `DeleteAccountRequest`
- [ ] Create `app/api/routes/users.py`:
  - `GET /api/users/me`
  - `PATCH /api/users/me` — update name
  - `POST /api/users/me/password` — verify current password first
  - `POST /api/users/me/api-key` — test key against Anthropic, then encrypt and save
  - `DELETE /api/users/me/api-key`
  - `DELETE /api/users/me` — verify password, delete cascade
- [ ] Write pytest tests for all user routes including ownership and wrong-password cases

### 1.9 Authentication — Frontend (both frontends)

**[React] `apps/web-react`:**
- [ ] Bootstrap: `cd apps/web-react && npm create vite@latest . -- --template react-ts`
- [ ] Install all React frontend dependencies (see 04_LIBRARIES_AND_FRAMEWORKS.md §React)
- [ ] Create `src/stores/authStore.ts` — Zustand persisted store (`user`, `accessToken`)
- [ ] Create `src/services/api.ts` — Axios instance, Bearer interceptor, 401 auto-refresh interceptor (see 07_FRONTEND_IMPLEMENTATION.md §2)
- [ ] Create `src/components/auth/ProtectedRoute.tsx` — redirects to `/login` if no token
- [ ] Create `src/components/auth/ApiKeyGuard.tsx` — redirects to `/settings?prompt=api-key` if `!user.has_api_key`
- [ ] Create `/login` and `/register` pages with Zod + React Hook Form
- [ ] Setup `QueryClientProvider` in `src/main.tsx`
- [ ] Setup router in `src/App.tsx` (see 07_FRONTEND_IMPLEMENTATION.md §4)

**[Svelte] `apps/web-svelte`:**
- [ ] Bootstrap: `cd apps/web-svelte && npm create svelte@latest .` (TypeScript, Skeleton project)
- [ ] Install all SvelteKit frontend dependencies (see 04_LIBRARIES_AND_FRAMEWORKS.md §SvelteKit)
- [ ] Create `src/lib/stores/authStore.ts` — Svelte writable store with localStorage persistence
- [ ] Create `src/lib/services/api.ts` — Axios instance, Bearer interceptor, 401 auto-refresh interceptor (see 07_FRONTEND_IMPLEMENTATION_SVELTE.md §6)
- [ ] Create `src/routes/(protected)/+layout.ts` — auth guard via `load()` + `redirect()`
- [ ] Create `src/routes/(protected)/(requires-api-key)/+layout.ts` — API key guard
- [ ] Create `login/+page.svelte` and `register/+page.svelte` with Zod + SuperForms
- [ ] Configure SPA mode: `export const ssr = false` in root `+layout.ts`

### 1.10 Settings Page — Frontend (both frontends)
Both versions implement four identical sections: Profile, API Key, Security, Danger Zone.
- [ ] [React] Create `/settings` page — see 07_FRONTEND_IMPLEMENTATION.md
- [ ] [Svelte] Create `settings/+page.svelte` — see 07_FRONTEND_IMPLEMENTATION_SVELTE.md §16
- [ ] Show API key setup banner on Dashboard when `user.has_api_key === false` (both)

### 1.11 Basic Chat UI (both frontends)
- [ ] [React] Install `react-resizable-panels`; build `ChatPanel.tsx`, `MessageBubble.tsx`, `ChatInput.tsx`, `SplitLayout.tsx`; create `chatStore.ts` (Zustand)
- [ ] [Svelte] Install `svelte-splitpanes`; build `ChatPanel.svelte`, `MessageBubble.svelte`, `ChatInput.svelte`, `SplitLayout.svelte`; create `chatStore.ts` (writable)
- [ ] Both: stub `POST /api/chat` returning a mock SSE stream (wired up fully in Phase 2)
- [ ] Both: typing indicator while `isStreaming`

### 1.12 Model Selector
- [ ] `GET /api/models` endpoint (public, no auth) → `ModelInfo[]`
- [ ] [React] `ModelSelector.tsx` using Radix Select
- [ ] [Svelte] `ModelSelector.svelte` using Melt UI `createSelect`
- [ ] Both: `sessionStore.selectedModel` — persisted to DB on change via `PATCH /api/sessions/:id`

### 1.13 New Analysis Flow (both frontends)
- [ ] Both: "New Analysis" button on Dashboard → `NewAnalysisModal`
- [ ] Both: Modal submits → `POST /api/sessions { idea, selected_model }` → navigate to `/session/:id`
- [ ] [React] `Session.tsx` mount: auto-send idea if `messages.length === 0` (guarded by `useRef(false)`)
- [ ] [Svelte] `session/[id]/+page.svelte`: auto-send via reactive `$:` block guarded by `let initialMessageSent = false`
- [ ] Both: `isStreaming` set to `true` immediately on auto-send — prevents double submit

### 1.14 System Prompt
- [ ] Create `app/prompts/analysis_system.py` — full prompt (see 08_LLM_AND_PROMPT.md §1)
- [ ] Test across all 3 model tiers with 10 diverse ideas before Phase 2

---

## PHASE 2 — Analysis Engine

### 2.1 Pydantic Graph Schemas
- [ ] Create `app/schemas/graph.py` with all types (see 03_ARCHITECTURE.md §6)
- [ ] **Critical:** `AddNodeAction` payload must use `NodePayload` (no `position` field), NOT `AnalysisNode`:
  ```python
  class NodePayload(BaseModel):
      """Used in AddNodeAction — position is assigned by frontend, not LLM."""
      id: str
      type: DimensionType
      label: str
      content: str
      score: float | None = Field(None, ge=0, le=10)
      parent_id: str | None = None
      # NOTE: no position field — frontend assigns position via graphLayout.ts

  class AddNodeAction(BaseModel):
      action: Literal["add"]
      payload: NodePayload   # NOT AnalysisNode
  ```
- [ ] Mirror all schemas as Zod in both frontends:
  - [React] `apps/web-react/src/schemas/graph.ts`
  - [Svelte] `apps/web-svelte/src/lib/schemas/graph.ts`
  - Both: `NodePayload` schema has no `position` field
- [ ] `AnalysisNode` (used in graph store + flow library) = `NodePayload` + `position: { x, y }`

### 2.2 LLM Service
- [ ] Create `app/services/llm_service.py`:
  - `get_user_api_key(user) -> str` — decrypt; raise HTTP 400 if not set
  - `build_messages(messages, graph_state, user_message, context_summary, covers_up_to) -> list[dict]`
  - `stream_response(messages, model, api_key) -> AsyncGenerator` using queue-based heartbeat pattern (see 06_BACKEND_IMPLEMENTATION.md §8)
  - `parse_llm_response(raw_text) -> LLMResponse`
  - `summarize_messages(messages, api_key) -> str` — always uses `claude-haiku-4-5`

### 2.3 SSE Streaming Chat Endpoint
- [ ] Create `app/schemas/chat.py` — `ChatRequest` with model allowlist validator + graph size validator
- [ ] Implement `POST /api/chat` as `StreamingResponse`:
  - Decrypt user API key; if missing → SSE error event + done
  - Check `Last-Event-ID` for reconnection replay
  - Run context summarization if needed
  - Use queue-based heartbeat: LLM generator and ping task both push to `asyncio.Queue`
  - Emit `event: token`, `event: graph_action`, `event: ping`, `event: error`, `event: done`
  - Set headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
  - Persist messages after stream completes (see §2.5 for concurrency-safe indexing)
- [ ] Map Anthropic error types to user-facing SSE error messages

### 2.4 SSE Reconnection
- [ ] Every SSE event includes `id: <message_uuid>` field
- [ ] Store `message_uuid` as the assistant `Message.id` in DB on persist
- [ ] On request with `Last-Event-ID` header: query DB for completed message by that ID; replay if found

### 2.5 Message Persistence — Concurrency-Safe Indexing
- [ ] `message_index` must be assigned with `SELECT FOR UPDATE` to prevent race conditions:
  ```python
  async with db.begin():
      result = await db.execute(
          select(func.max(Message.message_index))
          .where(Message.session_id == session_id)
          .with_for_update()
      )
      next_index = (result.scalar() or -1) + 1
  ```
- [ ] User message gets `message_index = next_index`, assistant gets `next_index + 1`
- [ ] Both messages inserted in the same transaction

### 2.6 Context Window Management
- [ ] In `POST /api/chat`, before building messages:
  - If `len(session.messages) > CONTEXT_WINDOW_MAX_MESSAGES` and `not session.context_summary`:
    - `to_summarize = messages[:-CONTEXT_WINDOW_MAX_MESSAGES]`
    - Call `summarize_messages()` on `to_summarize`
    - Save summary to `session.context_summary`
    - Save `session.context_summary_covers_up_to = to_summarize[-1].message_index` (the last index summarized, not the count)
- [ ] Pass summary to `build_messages()` — injected as user/assistant pair before recent messages
- [ ] System messages (`role='system'`) converted to `role='user'` with `[Context]: ` prefix in `build_messages()`

### 2.7 Session CRUD — Backend
- [ ] Create `app/schemas/session.py` — `SessionCreate`, `SessionResponse`, `SessionListItem` (paginated), `SessionUpdate`, `GraphStateUpdate`
- [ ] Create `app/api/routes/sessions.py`:
  - `GET /api/sessions?page=1&limit=20` — paginated, ordered by `updated_at` desc
  - `POST /api/sessions { idea, selected_model }` — creates session with root node pre-populated in `graph_state`
  - `GET /api/sessions/{id}` — returns session + all messages + graph_state; 403 if not owner
  - `PATCH /api/sessions/{id}` — name, selected_model
  - `DELETE /api/sessions/{id}`
  - `PUT /api/sessions/{id}/graph` — replaces JSONB graph_state
- [ ] All routes: 403 (not 404) when session exists but belongs to different user — prevents enumeration

### 2.8 Graph State Payload Guard
- [ ] `ChatRequest` field_validator: max 200 nodes, max 400 edges
- [ ] Both frontends: `graphGuards.ts` — warn at 150 nodes, hard stop UI at 200
  - [React] `apps/web-react/src/utils/graphGuards.ts`
  - [Svelte] `apps/web-svelte/src/lib/utils/graphGuards.ts`

### 2.9 Session Persistence — Frontend (both frontends)
- [ ] Both: `sessionStore.ts` — full CRUD + debounced `saveGraph()` (1s)
- [ ] Both: fetch sessions on Dashboard mount — store in `sessionStore.sessions`
- [ ] Both: fetch session on Session page mount — restore messages + graph + model
- [ ] Both: Loading state on Session page: skeleton while session loads; error state if 404/403

### 2.10 Test Suite
- [ ] `tests/conftest.py` — full fixtures: `setup_test_db`, `db_session` (rollback), `client`, `test_user`, `authed_client`, `mock_anthropic` (see 06_BACKEND_IMPLEMENTATION.md §12)
- [ ] `tests/test_auth.py` — register, login, refresh, logout, token expiry
- [ ] `tests/test_users.py` — all user routes, ownership, wrong password, api key validation
- [ ] `tests/test_sessions.py` — CRUD, ownership (403 check), pagination
- [ ] `tests/test_chat.py` — streaming with mock Anthropic, graph action validation, error handling
- [ ] `tests/test_llm_service.py` — `parse_llm_response` (valid, malformed, missing block, empty), `build_messages` (with/without summary, system message coercion)

---

## PHASE 3 — Visualization

### 3.1 Graph Flow Setup — Controlled Pattern
Both frontends use the same controlled pattern: the graph store is the single source of
truth; the flow library renders from it. `nodeTypes` must be defined at module level in
both frameworks to prevent node remounting on re-render.

**[React]** — `@xyflow/react` (React Flow):
```typescript
// GraphPanel.tsx
const storeNodes = useGraphStore(s => s.nodes)
const storeEdges = useGraphStore(s => s.edges)

const rfNodes: Node[] = storeNodes.map(n => ({
  id: n.id, type: 'analysisNode', position: n.position ?? { x: 0, y: 0 }, data: n,
}))
const rfEdges: Edge[] = storeEdges.map(e => ({
  id: e.id, source: e.source, target: e.target, label: e.label, type: 'default',
}))

<ReactFlow nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes}
  onNodeDragStop={(_, node) => graphStore.setNodePosition(node.id, node.position)}
  onNodesDelete={(nodes) => nodes.forEach(n => graphStore.deleteNode(n.id))}
  onEdgesDelete={(edges) => edges.forEach(e => graphStore.deleteEdge(e.id))} />
```
- [ ] [React] Register custom node type: `nodeTypes` object defined **outside** the component
- [ ] [React] `AnalysisNodeComponent.tsx` — color-coded per DimensionType, icon, label, content preview, score badge for feasibility

**[Svelte]** — `@xyflow/svelte` (Svelte Flow):
```typescript
// GraphPanel.svelte — nodeTypes at module level; derived stores for rfNodes/rfEdges
const nodeTypes = { analysisNode: AnalysisNodeComponent }
const rfNodes = derived(graphStore, $g => $g.nodes.map(n => ({ id: n.id, type: 'analysisNode', position: n.position, data: n })))
const rfEdges = derived(graphStore, $g => $g.edges.map(e => ({ id: e.id, source: e.source, target: e.target, label: e.label })))
```
- [ ] [Svelte] Register custom node type at module level in `GraphPanel.svelte`
- [ ] [Svelte] `AnalysisNodeComponent.svelte` — same visual design as React version

### 3.2 Graph State Management (both frontends)
- [ ] [React] `graphStore.ts` — Zustand + immer (see 07_FRONTEND_IMPLEMENTATION.md §7)
- [ ] [Svelte] `graphStore.ts` — Svelte writable store (see 07_FRONTEND_IMPLEMENTATION_SVELTE.md §8)
- [ ] Both: `applyGraphActions` — Zod-validate each action before applying; skip invalid; log warning
- [ ] Both: Every mutation triggers debounced `sessionStore.saveGraph()`

### 3.3 Auto-Layout (both frontends — shared logic)
The `graphLayout.ts` utility is identical between both versions; only the import path alias differs.
- [ ] [React] `apps/web-react/src/utils/graphLayout.ts`
- [ ] [Svelte] `apps/web-svelte/src/lib/utils/graphLayout.ts`
- [ ] Both: `layoutGraph(nodes, edges)` using Dagre; called once on initial analysis
- [ ] Both: `getIncrementalPosition(existingNodes, parentId?)` — for nodes added after initial layout
- [ ] Both: User-dragged positions preserved — `setNodePosition` marks node `userPositioned: true`; `applyGraphActions` skips position on `update` for such nodes

### 3.4 Graph Animations (both frontends)
- [ ] [React] New nodes: fade-in + scale via CSS transition on React Flow node wrapper class
- [ ] [Svelte] New nodes: `transition:scale` and `transition:fade` from `svelte/transition`
- [ ] Both: Deleted nodes: 300ms fade-out before store removal
- [ ] Both: Updated nodes: 2s highlight pulse via CSS keyframe
- [ ] Both: After adding nodes: call flow library `fitView({ padding: 0.2 })` with 500ms delay

---

## PHASE 4 — User Interactions on Graph

### 4.1 Node Detail Panel (both frontends)
- [ ] [React] `NodeDetailPanel.tsx` — slide-over from right edge of graph panel on node click; close on Escape via `useEffect` + `mousedown` listener
- [ ] [Svelte] `NodeDetailPanel.svelte` — slide-over using `transition:fly`; close on Escape via `svelte:window on:keydown`
- [ ] Both: Editable fields: label (input), content (textarea), score (number input, feasibility only)
- [ ] Both: Save → `graphStore.updateNode()` → push system message to chatStore + DB
- [ ] Both: Delete → `graphStore.deleteNode()` → push system message → close panel

### 4.2 Graph Toolbar (both frontends)
- [ ] [React] `GraphToolbar.tsx` — floating panel inside GraphPanel
- [ ] [Svelte] `GraphToolbar.svelte` — floating panel inside GraphPanel
- [ ] Both: "Add Node" → `AddNodeModal`: DimensionType selector, label, content → `graphStore.addNode()` → push system message
- [ ] Both: "Add Edge" → toggle connect mode; click source node then target → `graphStore.addEdge()`
- [ ] Both: "Delete Selected" → delete selected nodes/edges from the flow library's selection state
- [ ] Both: "Fit View" → call flow library `fitView()`
- [ ] Both: "Auto Layout" → re-run Dagre on current graph, update all positions

### 4.3 Drag and Reposition (both frontends)
- [ ] Both: `onNodeDragStop` → `graphStore.setNodePosition(id, position)` + mark `userPositioned: true`
- [ ] Both: Debounced graph save on drag stop (500ms)

### 4.4 Graph → Chat Feedback Loop (both frontends)
- [ ] Both: Every manual graph mutation → push `role: 'system'` message to `chatStore.messages` AND persist to DB
- [ ] Both: Message format: `[User action: edited node "Benefits › Faster delivery"]`
- [ ] Both: System messages displayed in chat as italic muted text, no avatar

### 4.5 Node Context Menu (both frontends)
- [ ] [React] Right-click node → Radix `ContextMenu`: "Edit", "Delete", "Ask Claude about this"
- [ ] [Svelte] Right-click node → Melt UI `createContextMenu`: "Edit", "Delete", "Ask Claude about this"
- [ ] Both: "Ask Claude" → pre-fills ChatInput value: `Tell me more about: [node.label]`

---

## PHASE 5 — Polish and Production

### 5.1 Dashboard Page (both frontends)
- [ ] Both: Session cards: name, idea excerpt (60 chars), model badge, `updated_at` relative time
- [ ] Both: Sort by `updated_at` desc; paginated (20/page); infinite scroll or "Load more"
- [ ] Both: Delete button on card hover → confirmation toast ("Undo" within 5s)
- [ ] Both: API key missing banner at top (yellow/warning color)
- [ ] Both: Empty state: illustration + "No analyses yet. Start your first one →"

### 5.2 UI Polish (both frontends)
- [ ] [React] `AppHeader.tsx` — logo, session name (double-click to rename), model badge, user avatar dropdown
- [ ] [Svelte] `AppHeader.svelte` — same structure
- [ ] Both: Loading skeleton for session list cards on Dashboard
- [ ] Both: Loading skeleton for session workspace while `GET /api/sessions/:id` resolves
- [ ] Both: Empty state in GraphPanel: "Your analysis will appear here"
- [ ] Both: Empty state in ChatPanel: "Describe your idea to begin"
- [ ] Both: Toast notifications: session saved, node added, errors, delete undo
- [ ] Both: Keyboard shortcuts: `Cmd/Ctrl+Enter` to send, `Escape` to close panels/modals

### 5.3 Error Handling (both frontends)
- [ ] [React] React `ErrorBoundary` wrapping the workspace route
- [ ] [Svelte] `<svelte:boundary>` (Svelte 5) or try/catch in load functions
- [ ] Both: SSE error events → inline error in chat with "Retry" button
- [ ] Both: 404 page for unmatched routes
- [ ] Backend: FastAPI global exception handler → always returns JSON (never HTML 500 pages)
- [ ] Both: Session load 404/403 → redirect to Dashboard with toast

### 5.4 Security Hardening
- [ ] `slowapi` limits: `/auth/*` 5/15min per IP; `/api/chat` 30/min per user; `/api/sessions/*` 60/min per user
- [ ] Security headers middleware (see 06_BACKEND_IMPLEMENTATION.md §14)
- [ ] Middleware order in `app/main.py`: SecurityHeaders → CORS → routes (see §1.4)
- [ ] CORS `allow_origins` list in production: only the deployed frontend origin(s)
- [ ] Model allowlist in Pydantic validator
- [ ] Never log decrypted API keys or JWT secrets

### 5.5 Testing (both frontends + backend)
- [ ] All backend unit + integration tests (see §2.10)
- [ ] [React] Vitest for `graphStore.applyGraphActions` — all 4 action types, invalid action skipped, Zod validation
- [ ] [React] Vitest for SSE parser in `chatService.ts`
- [ ] [Svelte] Vitest + `@testing-library/svelte` for `graphStore.applyGraphActions`
- [ ] [Svelte] Vitest for SSE parser in `chatService.ts`
- [ ] [React] E2E Playwright: register → set API key → new analysis → graph renders → follow-up → manual node edit → settings → delete account
- [ ] [Svelte] E2E Playwright: same flow on port 3001

### 5.6 Docker — Production Builds
- [ ] `apps/api/Dockerfile` (multi-stage with `development` and `production` targets):
  ```dockerfile
  FROM python:3.12-slim AS base
  WORKDIR /app
  RUN pip install uv

  FROM base AS development
  COPY pyproject.toml .
  RUN uv sync
  COPY . .
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  FROM base AS production
  COPY pyproject.toml .
  RUN uv sync --no-dev --frozen
  COPY app/ app/
  COPY alembic/ alembic/
  COPY alembic.ini .
  ENV PATH="/app/.venv/bin:$PATH"
  EXPOSE 8000
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
  ```

- [ ] [React] `apps/web-react/Dockerfile` (multi-stage — nginx serves static build):
  ```dockerfile
  FROM node:20-alpine AS development
  WORKDIR /app
  COPY package*.json .
  RUN npm ci
  CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

  FROM node:20-alpine AS builder
  WORKDIR /app
  COPY package*.json .
  RUN npm ci
  COPY . .
  RUN npm run build

  FROM nginx:alpine AS production
  COPY --from=builder /app/dist /usr/share/nginx/html
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  EXPOSE 80
  ```

- [ ] [React] `apps/web-react/nginx.conf` (SSE location block before `/api/`):
  ```nginx
  server {
      listen 80;
      server_name _;

      location /api/chat {
          proxy_pass http://api:8000/api/chat;
          proxy_http_version 1.1;
          proxy_set_header Connection '';
          proxy_buffering off;
          proxy_cache off;
          proxy_read_timeout 120s;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }

      location /api/ {
          proxy_pass http://api:8000/api/;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }

      location /auth/ {
          proxy_pass http://api:8000/auth/;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }

      location / {
          root /usr/share/nginx/html;
          index index.html;
          try_files $uri /index.html;
      }
  }
  ```

- [ ] [Svelte] `apps/web-svelte/Dockerfile` (multi-stage — adapter-node runs as Node server):
  ```dockerfile
  FROM node:20-alpine AS development
  WORKDIR /app
  COPY package*.json .
  RUN npm ci
  CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3001"]

  FROM node:20-alpine AS builder
  WORKDIR /app
  COPY package*.json .
  RUN npm ci
  COPY . .
  ENV PUBLIC_API_URL=""
  RUN npm run build

  FROM node:20-alpine AS production
  WORKDIR /app
  COPY --from=builder /app/build ./build
  COPY --from=builder /app/package*.json .
  RUN npm ci --omit=dev
  ENV PORT=3000
  ENV HOST=0.0.0.0
  EXPOSE 3000
  CMD ["node", "build/index.js"]
  # PORT=3000 in production — matches the React container port so the ALB
  # target group config and sg-web inbound rule are the same regardless of
  # which frontend is deployed. PORT=3001 is local dev only.
  ```

- [ ] [Svelte] Note: in production the ALB or a dedicated nginx reverse proxy handles routing `/api/` and `/auth/` to the API container; the SvelteKit Node server only serves frontend routes. See 07_FRONTEND_IMPLEMENTATION_SVELTE.md §22 for the nginx config.

### 5.7 Terraform — AWS Infrastructure
- [ ] Bootstrap S3 + DynamoDB for Terraform state (see 05_INFRASTRUCTURE_AND_DEPLOYMENT.md §6)
- [ ] Implement all Terraform modules (see 05_INFRASTRUCTURE_AND_DEPLOYMENT.md §2)
- [ ] `terraform.tfvars`: api 512 CPU/1024 MB, web 256 CPU/512 MB, RDS db.t3.micro, ALB idle_timeout=60
- [ ] The single `web` ECS service/task definition targets whichever frontend image was last deployed — Terraform is frontend-agnostic; the image URI is passed in at deploy time
- [ ] `terraform plan && terraform apply`
- [ ] Run `alembic upgrade head` as one-off ECS task on first deploy

### 5.8 CI/CD
- [ ] `.github/workflows/ci.yml` (on PR): three parallel jobs:
  - `backend`: `ruff check`, `mypy`, `pytest`
  - `frontend-react`: `eslint`, `tsc --noEmit`, `vitest run` (in `apps/web-react`)
  - `frontend-svelte`: `svelte-check`, `vitest run` (in `apps/web-svelte`)
- [ ] `.github/workflows/deploy.yml` (on push to main):
  - Reads `DEPLOY_FRONTEND` secret (`react` or `svelte`) to determine which frontend to deploy
  - Builds and pushes the api image always
  - Builds and pushes only the selected frontend image
  - Runs migration task, then updates api and web ECS services
- [ ] GitHub Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REGISTRY`, `DEPLOY_FRONTEND`

### 5.9 Documentation
- [ ] Root `README.md`: overview, local setup (both frontends in dev), how to switch the deployed frontend, seed, env vars table, deploy guide
- [ ] `apps/web-react/README.md`: React-specific notes
- [ ] `apps/web-svelte/README.md`: SvelteKit-specific notes
- [ ] `infra/README.md`: Terraform bootstrap, first-time setup, how `DEPLOY_FRONTEND` controls which image the web ECS service runs
- [ ] `apps/api/app/prompts/README.md`: prompt design + changelog