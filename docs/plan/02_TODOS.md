---
doc: 02_TODOS
status: ready
version: 2
created: 2026-04-18
updated: 2026-04-19
scope: All granular checkbox tasks across 5 phases — the single mutable implementation tracker
relates_to:
  - 01_PROJECT_PLAN
  - 03_ARCHITECTURE
  - 05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT
  - 05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS
  - 06_BACKEND_IMPLEMENTATION
  - 07_FRONTEND_IMPLEMENTATION
  - 07_FRONTEND_IMPLEMENTATION_SVELTE
  - 08_LLM_AND_PROMPT
---

# TODOS — IdeaLens
**Stack:** SvelteKit · TypeScript · Python 3.12 · FastAPI · PostgreSQL · SQLAlchemy 2.x async · Anthropic SDK · AWS App Runner

> Frontend implementation: SvelteKit version → 07_FRONTEND_IMPLEMENTATION_SVELTE.md
> Backend implementation details: see 06_BACKEND_IMPLEMENTATION.md, 08_LLM_AND_PROMPT.md
> Infrastructure details: see 05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS.md (AWS · App Runner + RDS)
>                         see 05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT.md (Non-AWS · Railway + Neon + Vercel)
>
> Notation: tasks marked [React] are React-only and not built (SvelteKit was chosen instead).
> [x] = done · [ ] = not done · [-] = N/A with reason

---

## PHASE 1 — Foundation

### 1.1 Project Scaffolding
- [x] Create root monorepo structure (backend/ + frontend/ layout)
- [x] Create root `.gitignore`
- [x] Initialize Git repository at monorepo root
- [x] Create `backend/.env.example`
- [-] [React] Create `/apps/web-react/.env.example` — React frontend not built; SvelteKit chosen
- [x] [Svelte] Create `frontend/.env.example` (via `.env.development`)

### 1.2 docker-compose.yml
- [x] `infra/docker-compose.dev.yml` with postgres + healthcheck
- [-] [React] `apps/web-react/Dockerfile` — React frontend not built
- [x] [Svelte] `infra/Dockerfile.frontend` (production Dockerfile)

### 1.3 Environment Variables

**[React] `apps/web-react`:**
- [-] Create `apps/web-react/.env.development` — React frontend not built
- [-] Create `apps/web-react/.env.production` — React frontend not built
- [-] Create `apps/web-react/src/config.ts` — React frontend not built
- [-] Configure `apps/web-react/vite.config.ts` — React frontend not built

**[Svelte] `frontend`:**
- [x] Create `frontend/.env.development`: `PUBLIC_API_URL=http://localhost:8000`
- [x] Create `frontend/.env.production`: `PUBLIC_API_URL=` (intentionally empty)
- [x] Create `frontend/src/lib/config.ts`
- [x] Configure `frontend/vite.config.ts`
- [x] Create `frontend/src/routes/+layout.ts` with `export const ssr = false`

### 1.4 Backend Base Setup
- [x] `uv init && uv venv`
- [x] Install all dependencies (fastapi, uvicorn, sqlalchemy, alembic, jose, bcrypt, cryptography, anthropic, slowapi, etc.)
- [x] Run `uv lock`
- [x] Configure `pyproject.toml` (pytest, ruff, coverage)
- [x] Create `app/core/config.py` — pydantic-settings `Settings` with `get_settings()` lru_cache singleton
- [x] Create `app/main.py` — `create_app()` factory with SecurityHeadersMiddleware, CORSMiddleware, slowapi
- [x] Add `GET /health` endpoint
- [x] Configure `structlog`

### 1.5 Database Setup — SQLAlchemy + Alembic Async
- [x] Create `app/db/models/__init__.py` — imports all models for Alembic discovery
- [x] Create `app/db/models/base.py`
- [x] Create all four models (User, RefreshToken, Session, Message) with correct `onupdate=func.now()`
- [x] Create `app/db/session.py` — `get_db` async generator dependency
- [x] Initialize Alembic and configure `alembic/env.py` for async
- [x] Generate and apply initial migration
- [x] Create `app/db/seed.py` — idempotent seed script

### 1.6 API Key Encryption Service
- [x] Create `app/services/encryption_service.py` using `cryptography.fernet.Fernet`
- [x] Add `API_KEY_ENCRYPTION_KEY` to `.env.example`

### 1.7 Authentication — Backend
- [x] Create `app/schemas/auth.py`
- [x] Create `app/services/auth_service.py` — bcrypt hash/verify, JWT create/verify
- [x] Create `app/api/routes/auth.py` — register, login, refresh, logout
- [x] Refresh token httpOnly cookie set identically in register AND login
- [x] Create `app/dependencies/auth.py` — `get_current_user` dependency
- [x] Write pytest tests (register, login, refresh, logout, token expiry, invalid JWT, deleted-user token)

### 1.8 User Settings — Backend
- [x] Create `app/schemas/user.py` — `UpdateProfileRequest`, `ChangePasswordRequest`, `SetApiKeyRequest` (validates `sk-ant-` prefix), `DeleteAccountRequest`
- [x] Create `app/api/routes/users.py` — GET/PATCH/DELETE me, password, api-key
- [x] Write pytest tests for all user routes including api key validation flow

### 1.9 Authentication — Frontend
- [-] [React] Bootstrap + install React dependencies — React frontend not built
- [x] [Svelte] Bootstrap SvelteKit + install all dependencies
- [x] [Svelte] Create `src/lib/stores/authStore.ts` — writable store with localStorage persistence
- [x] [Svelte] Create `src/lib/services/api.ts` — fetch wrapper with Bearer token
- [x] [Svelte] Create `src/routes/(protected)/+layout.ts` — auth guard via `load()` + `redirect()`
- [x] [Svelte] Create `src/routes/(protected)/(requires-api-key)/+layout.ts` — API key guard
- [x] [Svelte] Create `login/+page.svelte` and `register/+page.svelte`
- [x] Configure SPA mode: `export const ssr = false` in root `+layout.ts`

### 1.10 Settings Page — Frontend
- [-] [React] Create `/settings` page — React frontend not built
- [x] [Svelte] Create `settings/+page.svelte` (Profile, API Key, Security, Danger Zone sections)
- [x] Show API key setup banner on Dashboard when `user.has_api_key === false`

### 1.11 Basic Chat UI
- [-] [React] ChatPanel, MessageBubble, ChatInput, SplitLayout, chatStore (Zustand) — React frontend not built
- [x] [Svelte] ChatPanel, MessageBubble, ChatInput, SplitLayout, chatStore (writable)
- [x] SSE stream wired up to chat
- [x] Typing indicator while `isStreaming`

### 1.12 Model Selector
- [x] `GET /api/models` endpoint (public, no auth)
- [-] [React] `ModelSelector.tsx` — React frontend not built
- [x] [Svelte] `ModelSelector.svelte`
- [x] `sessionStore.selectedModel` — persisted to DB on change via `PATCH /api/sessions/:id`

### 1.13 New Analysis Flow
- [x] "New Analysis" button on Dashboard → `NewAnalysisModal` (inlined in +page.svelte)
- [x] Modal submits → `POST /api/sessions` → navigate to `/session/:id`
- [-] [React] auto-send idea guarded by `useRef(false)` — React frontend not built
- [x] [Svelte] auto-send via `$effect` guarded by `let initialMessageSent = false`
- [x] `isStreaming` set to `true` immediately on auto-send

### 1.14 System Prompt
- [x] Create `app/prompts/analysis_system.py`
- [-] Test across all 3 model tiers with 10 diverse ideas before Phase 2 — requires live API keys; not a code task

---

## PHASE 2 — Analysis Engine

### 2.1 Pydantic Graph Schemas
- [x] Create `app/schemas/graph.py` with all types
- [x] `AddNodeAction` payload uses `NodePayload` (no `position` field)
- [-] [React] Mirror schemas as Zod in `apps/web-react/src/schemas/graph.ts` — React frontend not built
- [x] [Svelte] Mirror schemas as Zod in `frontend/src/lib/schemas/graph.ts`

### 2.2 LLM Service
- [x] Create `app/services/llm_service.py`:
  - [x] `build_messages()` with context summary injection
  - [x] `stream_with_heartbeat()` using queue-based heartbeat pattern
  - [x] `parse_llm_response()` with Pydantic validation
  - [x] `summarize_messages()` using claude-haiku-4-5
  - [x] `persist_messages()` — concurrency-safe indexing

### 2.3 SSE Streaming Chat Endpoint
- [x] Create `app/schemas/chat.py` — `ChatRequest` with model allowlist + graph size validators
- [x] Implement `POST /api/chat` as `StreamingResponse`
  - [x] Decrypt user API key; if missing → SSE error event + done
  - [x] Check `Last-Event-ID` for reconnection replay
  - [x] Run context summarization if needed (with post-commit lazy-load fix)
  - [x] Queue-based heartbeat: LLM generator + ping task
  - [x] Emit `token`, `graph_action`, `ping`, `error`, `done` events
  - [x] SSE headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
  - [x] Persist messages after stream completes
- [x] Map Anthropic error types to user-facing SSE error messages (529 → friendly message)

### 2.4 SSE Reconnection
- [x] Every SSE event includes `id: <message_uuid>` field
- [x] Store `message_uuid` as the assistant `Message.id` in DB on persist
- [x] On request with `Last-Event-ID` header: query DB, replay if found

### 2.5 Message Persistence — Concurrency-Safe Indexing
- [x] `message_index` assigned via `SELECT MAX` + `WITH FOR UPDATE`
- [x] User message gets `next_index`, assistant gets `next_index + 1`
- [x] Both messages inserted in the same transaction

### 2.6 Context Window Management
- [x] Summarize when `len(session.messages) > CONTEXT_WINDOW_MAX_MESSAGES`
- [x] Pass summary to `build_messages()` as context injection
- [x] System messages converted to `role='user'` with `[Context]: ` prefix

### 2.7 Session CRUD — Backend
- [x] Create `app/schemas/session.py`
- [x] Create `app/api/routes/sessions.py`:
  - [x] `GET /api/sessions` — paginated, ordered by `updated_at` desc
  - [x] `POST /api/sessions` — creates session with root node pre-populated
  - [x] `GET /api/sessions/{id}` — returns session + all messages + graph_state
  - [x] `PATCH /api/sessions/{id}` — name, selected_model
  - [x] `DELETE /api/sessions/{id}`
  - [x] `PUT /api/sessions/{id}/graph` — replaces JSONB graph_state
  - [x] `POST /api/sessions/{id}/messages` — persists system messages from user graph actions
- [x] All routes: 403 when session belongs to different user

### 2.8 Graph State Payload Guard
- [x] `ChatRequest` field_validator: max 200 nodes, max 400 edges
- [-] [React] `graphGuards.ts` — React frontend not built
- [x] [Svelte] `frontend/src/lib/utils/graphGuards.ts` — warn at 150 nodes, hard stop at 200

### 2.9 Session Persistence — Frontend
- [-] [React] sessionStore CRUD + debounced saveGraph — React frontend not built
- [x] [Svelte] `sessionStore.ts` — full CRUD + debounced `saveGraph()` (1s)
- [x] Fetch sessions on Dashboard mount
- [x] Fetch session on Session page mount — restore messages + graph + model
- [x] Loading state on Session page; error state redirects to Dashboard

### 2.10 Test Suite
- [x] `tests/conftest.py` — NullPool per-test engine, SAVEPOINT isolation, `expire_on_commit=False`
- [x] `tests/test_auth.py` — register, login, refresh, logout, token expiry, invalid JWT, deleted-user token
- [x] `tests/test_users.py` — all user routes, ownership, wrong password, api key validation (mock Anthropic)
- [x] `tests/test_sessions.py` — CRUD, ownership (403), pagination, graph update, add system message
- [x] `tests/test_chat.py` — SSE stream (mocked LLM), graph actions, error handling, reconnect replay, context summarization
- [x] `tests/test_services.py` — `parse_llm_response`, `build_messages`, `stream_with_heartbeat`, `summarize_messages`, `persist_messages`
- [x] `tests/test_schemas.py` — graph schema validators, `ChatRequest` validators, `SetApiKeyRequest`

---

## PHASE 3 — Visualization

### 3.1 Graph Flow Setup — Controlled Pattern
- [-] [React] `GraphPanel.tsx` with `@xyflow/react`; `AnalysisNodeComponent.tsx` — React frontend not built
- [x] [Svelte] `GraphPanel.svelte` with `@xyflow/svelte`; `AnalysisNodeComponent.svelte`
- [x] [Svelte] `nodeTypes` defined at module level to prevent remounting

### 3.2 Graph State Management
- [-] [React] `graphStore.ts` (Zustand + immer) — React frontend not built
- [x] [Svelte] `graphStore.ts` — Svelte writable store with all mutations + `applyGraphActions`
- [x] `applyGraphActions` — Zod-validate each action before applying
- [x] Every mutation triggers debounced `sessionStore.saveGraph()`

### 3.3 Auto-Layout
- [-] [React] `apps/web-react/src/utils/graphLayout.ts` — React frontend not built
- [x] [Svelte] `frontend/src/lib/utils/graphLayout.ts` — Dagre layout, respects `userPositioned`
- [x] User-dragged positions preserved — `setNodePosition` marks `userPositioned: true`
- [x] `getIncrementalPosition()` — separate helper for nodes added after initial layout

### 3.4 Graph Animations
- [-] [React] New nodes: fade-in + scale via CSS transition — React frontend not built
- [x] [Svelte] New nodes: `in:scale` transition from `svelte/transition`
- [-] Both: Deleted nodes: 300ms fade-out before store removal — requires deferring store removal; deferred for post-MVP
- [-] Both: Updated nodes: 2s highlight pulse via CSS keyframe — nice-to-have; deferred for post-MVP
- [-] Both: After adding nodes: `fitView()` with 500ms delay — requires SvelteFlow instance access from outside component; deferred

---

## PHASE 4 — User Interactions on Graph

### 4.1 Node Detail Panel
- [-] [React] `NodeDetailPanel.tsx` — slide-over, Escape to close — React frontend not built
- [x] [Svelte] `NodeDetailPanel.svelte` — panel, Escape via `svelte:window`
- [x] Editable fields: label (inline in header), content (textarea with edit/cancel)
- [x] Save → `graphStore.updateNode()` + `sessionStore.saveGraph()`
- [x] Delete → `graphStore.deleteNode()` + close panel
- [x] Save/Delete → push system message to chatStore + persist to DB via `POST /api/sessions/{id}/messages`
- [x] "Ask Claude" button → pre-fills ChatInput with `Tell me more about: [node.label]`

### 4.2 Graph Toolbar
- [-] [React] `GraphToolbar.tsx` — React frontend not built
- [x] [Svelte] `GraphToolbar.svelte` — floating panel in GraphPanel
- [x] "Fit View" → `fitView()`
- [x] "Auto Layout" → re-run Dagre on current graph
- [x] "Add Node" → `AddNodeModal` with DimensionType selector + system message push
- [-] "Add Edge" → toggle connect mode, click source then target — requires SvelteFlow connection mode toggle; deferred for post-MVP
- [x] "Delete Selected" → delete selected node from store + save graph

### 4.3 Drag and Reposition
- [x] `onnodedragstop` → `graphStore.setNodePosition()` + mark `userPositioned: true`
- [x] Debounced graph save on drag stop

### 4.4 Graph → Chat Feedback Loop
- [x] Manual graph mutations → push `role: 'system'` message to chatStore AND persist to DB
- [x] Message format: `[User action: edited node "Benefits › Faster delivery"]`
- [x] System messages displayed in chat as italic muted text (MessageBubble handles `role === 'system'`)

### 4.5 Node Context Menu
- [-] [React] Right-click → Radix ContextMenu — React frontend not built
- [-] [Svelte] Right-click node → context menu — deferred; node detail panel + Ask Claude button already cover the key actions

---

## PHASE 5 — Polish and Production

### 5.1 Dashboard Page
- [x] Session cards: name, idea excerpt, model badge, relative time
- [x] Sort by `updated_at` desc
- [-] Paginated (20/page) infinite scroll or "Load more" — first 20 sessions shown; sufficient for MVP; pagination API supported but no "load more" UI
- [x] Delete button → confirmation toast with "Undo" within 5s
- [x] API key missing banner (yellow/warning)
- [x] Empty state

### 5.2 UI Polish
- [-] [React] `AppHeader.tsx` — React frontend not built
- [x] [Svelte] `AppHeader.svelte` — logo, session name (double-click to rename), model badge
- [-] User avatar dropdown menu — user name shown in header; dropdown deferred for post-MVP
- [x] Loading skeleton for session list cards on Dashboard
- [x] Loading skeleton for session workspace while session loads
- [x] Empty state in GraphPanel
- [x] Empty state in ChatPanel
- [x] Toast notifications (svelte-sonner)
- [x] Keyboard shortcuts: `Cmd/Ctrl+Enter` to send; `Escape` to close node detail panel

### 5.3 Error Handling
- [-] [React] React `ErrorBoundary` — React frontend not built
- [x] [Svelte] `<svelte:boundary>` wrapping workspace route
- [x] SSE error events → inline error in chat
- [x] 404 page (`+error.svelte`) for unmatched routes
- [x] Backend: FastAPI global exception handler
- [x] Session load 404/403 → redirect to Dashboard with toast

### 5.4 Security Hardening
- [x] `slowapi` integrated into app
- [x] Rate limits applied on routes: `/auth/*` 5/15min, `/api/chat` 30/min, `/api/sessions/*` 60/min
- [x] Security headers middleware (X-Content-Type-Options, X-Frame-Options, HSTS in prod)
- [x] Middleware order: SecurityHeaders → CORS → routes
- [x] CORS `allow_origins` configurable via settings
- [x] Model allowlist in Pydantic validator
- [x] Never log decrypted API keys or JWT secrets

### 5.5 Testing
- [x] All backend unit + integration tests (104 tests, 99% coverage — note: tests require PostgreSQL; see CI notes)
- [-] [React] Vitest for graphStore, SSE parser — React frontend not built
- [x] [Svelte] Vitest for `graphStore.applyGraphActions` — all 4 action types (22 tests)
- [x] [Svelte] Vitest for stores (chatStore), schemas (graph Zod), utilities (debounce, graphLayout, graphGuards)
- [x] [Svelte] Vitest for SSE parser in `chatService.ts` (8 tests with fetch mock)
- [-] [React] E2E Playwright — React frontend not built
- [-] [Svelte] E2E Playwright — requires live infrastructure; deferred for post-MVP

### 5.6 Docker — Production Builds
- [x] `infra/Dockerfile.backend` (multi-stage with uv builder)
- [-] [React] `apps/web-react/Dockerfile` — React frontend not built
- [x] [Svelte] `infra/Dockerfile.frontend` (multi-stage Bun builder + Node runner)
- [x] `infra/Dockerfile.frontend` production stage uses `ARG PUBLIC_API_URL` + `ENV PUBLIC_API_URL=$PUBLIC_API_URL` — baked in at image build time by deploy scripts

### 5.7 AWS Infrastructure — Terraform + EC2
> Decision: Using AWS App Runner instead of ECS + Terraform. See deploy/aws/ for the chosen approach.
- [-] Bootstrap S3 + DynamoDB for Terraform state — using App Runner instead; Terraform not needed
- [-] Implement all Terraform modules — using App Runner instead
- [-] `terraform.tfvars` — using App Runner instead
- [-] `terraform plan && terraform apply` — using App Runner instead
- [-] Run `alembic upgrade head` via SSH on first deploy — done manually post-deploy (see deploy/aws/README.md)

### 5.7b Non-AWS Alternative — Railway + Neon + Vercel
> AWS App Runner was chosen instead. These steps are documented in 05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT.md for reference.
- [-] All Railway + Neon + Vercel steps — using AWS App Runner instead

### 5.8 CI/CD
- [x] `.github/workflows/ci.yaml` — backend lint + test, frontend type-check + test + build, deploy script tests; triggers on push + PR
- [x] `.github/workflows/deploy.yml` — manual (`workflow_dispatch`) deploy to AWS App Runner; intentionally not on push to prevent accidental deployments
- [-] Auto-deploy on push to main — manual deploy chosen to prevent accidental production deployments

### 5.9 Documentation
- [x] Root `README.md`
- [x] `deploy/aws/README.md`: prerequisites, setup-infra → migrate → deploy sequence, secrets reference
- [x] `backend/app/prompts/README.md`: prompt design, 9 dimension types, graph action schema
