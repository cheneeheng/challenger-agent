---
doc: 02_TODOS
status: ready
version: 1
created: 2026-04-18
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
**Stack:** React 19 + Vite · SvelteKit · TypeScript · Python 3.12 · FastAPI · PostgreSQL · SQLAlchemy 2.x async · Anthropic SDK · AWS EC2

> Frontend implementation details:
>   React version    → 07_FRONTEND_IMPLEMENTATION.md
>   SvelteKit version → 07_FRONTEND_IMPLEMENTATION_SVELTE.md
> Backend implementation details: see 06_BACKEND_IMPLEMENTATION.md, 08_LLM_AND_PROMPT.md
> Infrastructure details: see 05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS.md (AWS · EC2 + S3/CloudFront + RDS)
>                         see 05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT.md (Non-AWS · Railway + Neon + Vercel)
>
> Notation: tasks marked [React] or [Svelte] are frontend-specific.
> Tasks with no tag apply to both frontends or to the shared backend/infra.
> [x] = done · [ ] = not done · [-] = N/A (React frontend not being built)

---

## PHASE 1 — Foundation

### 1.1 Project Scaffolding
- [x] Create root monorepo structure (backend/ + frontend/ layout, not apps/ — functionally equivalent)
- [x] Create root `.gitignore`
- [x] Initialize Git repository at monorepo root
- [x] Create `backend/.env.example`
- [-] [React] Create `/apps/web-react/.env.example`
- [x] [Svelte] Create `frontend/.env.example` (via `.env.development`)

### 1.2 docker-compose.yml
- [x] `docker-compose.yml` at repo root with postgres + healthcheck
- [-] [React] `apps/web-react/Dockerfile`
- [-] [Svelte] `apps/web-svelte/Dockerfile` (production Dockerfile exists at `infra/Dockerfile.frontend`)

### 1.3 Environment Variables

**[React] `apps/web-react`:**
- [-] Create `apps/web-react/.env.development`
- [-] Create `apps/web-react/.env.production`
- [-] Create `apps/web-react/src/config.ts`
- [-] Configure `apps/web-react/vite.config.ts`

**[Svelte] `apps/web-svelte`:**
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

### 1.9 Authentication — Frontend (both frontends)

**[React] `apps/web-react`:**
- [-] Bootstrap + install React dependencies
- [-] Create `src/stores/authStore.ts` (Zustand)
- [-] Create `src/services/api.ts` (Axios)
- [-] Create ProtectedRoute + ApiKeyGuard components
- [-] Create login + register pages
- [-] Setup QueryClientProvider + router

**[Svelte] `apps/web-svelte`:**
- [x] Bootstrap SvelteKit + install all dependencies
- [x] Create `src/lib/stores/authStore.ts` — writable store with localStorage persistence
- [x] Create `src/lib/services/api.ts` — fetch wrapper with Bearer token
- [x] Create `src/routes/(protected)/+layout.ts` — auth guard via `load()` + `redirect()`
- [x] Create `src/routes/(protected)/(requires-api-key)/+layout.ts` — API key guard
- [x] Create `login/+page.svelte` and `register/+page.svelte`
- [x] Configure SPA mode: `export const ssr = false` in root `+layout.ts`

### 1.10 Settings Page — Frontend (both frontends)
- [-] [React] Create `/settings` page
- [x] [Svelte] Create `settings/+page.svelte` (Profile, API Key, Security, Danger Zone sections)
- [x] Show API key setup banner on Dashboard when `user.has_api_key === false`

### 1.11 Basic Chat UI (both frontends)
- [-] [React] ChatPanel, MessageBubble, ChatInput, SplitLayout, chatStore (Zustand)
- [x] [Svelte] ChatPanel, MessageBubble, ChatInput, SplitLayout, chatStore (writable)
- [x] Both: SSE stream wired up to chat
- [x] Both: typing indicator while `isStreaming`

### 1.12 Model Selector
- [x] `GET /api/models` endpoint (public, no auth)
- [-] [React] `ModelSelector.tsx` using Radix Select
- [x] [Svelte] `ModelSelector.svelte` (plain `<select>` — Melt UI not installed)
- [x] `sessionStore.selectedModel` — persisted to DB on change via `PATCH /api/sessions/:id`

### 1.13 New Analysis Flow (both frontends)
- [x] Both: "New Analysis" button on Dashboard → `NewAnalysisModal` (inlined in +page.svelte)
- [x] Both: Modal submits → `POST /api/sessions` → navigate to `/session/:id`
- [-] [React] auto-send idea guarded by `useRef(false)`
- [x] [Svelte] auto-send via `onMount` guarded by `let initialMessageSent = false`
- [x] `isStreaming` set to `true` immediately on auto-send

### 1.14 System Prompt
- [x] Create `app/prompts/analysis_system.py`
- [-] Test across all 3 model tiers with 10 diverse ideas before Phase 2 (manual — requires live Anthropic key; deferred)

---

## PHASE 2 — Analysis Engine

### 2.1 Pydantic Graph Schemas
- [x] Create `app/schemas/graph.py` with all types
- [x] `AddNodeAction` payload uses `NodePayload` (no `position` field)
- [-] [React] Mirror schemas as Zod in `apps/web-react/src/schemas/graph.ts`
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
- [x] `message_index` assigned via `SELECT MAX` (note: `FOR UPDATE` removed — invalid with aggregate functions in PostgreSQL)
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
- [x] All routes: 403 when session belongs to different user

### 2.8 Graph State Payload Guard
- [x] `ChatRequest` field_validator: max 200 nodes, max 400 edges
- [-] [React] `graphGuards.ts`
- [x] [Svelte] `frontend/src/lib/utils/graphGuards.ts` — warn at 150 nodes, hard stop at 200

### 2.9 Session Persistence — Frontend (both frontends)
- [-] [React] sessionStore CRUD + debounced saveGraph
- [x] [Svelte] `sessionStore.ts` — full CRUD + debounced `saveGraph()` (1s)
- [x] Fetch sessions on Dashboard mount
- [x] Fetch session on Session page mount — restore messages + graph + model
- [x] Loading state on Session page; error state redirects to Dashboard

### 2.10 Test Suite
- [x] `tests/conftest.py` — NullPool per-test engine, SAVEPOINT isolation, `expire_on_commit=False`
- [x] `tests/test_auth.py` — register, login, refresh, logout, token expiry, invalid JWT, deleted-user token
- [x] `tests/test_users.py` — all user routes, ownership, wrong password, api key validation (mock Anthropic)
- [x] `tests/test_sessions.py` — CRUD, ownership (403), pagination, graph update
- [x] `tests/test_chat.py` — SSE stream (mocked LLM), graph actions, error handling, reconnect replay, context summarization
- [x] `tests/test_services.py` — `parse_llm_response`, `build_messages`, `stream_with_heartbeat`, `summarize_messages`, `persist_messages`
- [x] `tests/test_schemas.py` — graph schema validators, `ChatRequest` validators, `SetApiKeyRequest`

---

## PHASE 3 — Visualization

### 3.1 Graph Flow Setup — Controlled Pattern
- [-] [React] `GraphPanel.tsx` with `@xyflow/react`; `AnalysisNodeComponent.tsx`
- [x] [Svelte] `GraphPanel.svelte` with `@xyflow/svelte`; `AnalysisNodeComponent.svelte`
- [x] [Svelte] `nodeTypes` defined at module level to prevent remounting

### 3.2 Graph State Management (both frontends)
- [-] [React] `graphStore.ts` (Zustand + immer)
- [x] [Svelte] `graphStore.ts` — Svelte writable store with all mutations + `applyGraphActions`
- [x] Both: `applyGraphActions` — Zod-validate each action before applying (`llmGraphActionSchema.safeParse` per action)
- [x] Both: Every mutation triggers debounced `sessionStore.saveGraph()`

### 3.3 Auto-Layout (both frontends — shared logic)
- [-] [React] `apps/web-react/src/utils/graphLayout.ts`
- [x] [Svelte] `frontend/src/lib/utils/graphLayout.ts` — Dagre layout, respects `userPositioned`
- [x] User-dragged positions preserved — `setNodePosition` marks `userPositioned: true`
- [x] `getIncrementalPosition()` — separate helper in `graphLayout.ts`; called from `applyGraphActions`

### 3.4 Graph Animations (both frontends)
- [-] [React] New nodes: fade-in + scale via CSS transition
- [x] [Svelte] New nodes: `in:scale` transition in `AnalysisNodeComponent.svelte`
- [-] Both: Deleted nodes: 300ms fade-out — not feasible with controlled store pattern (nodes removed from store immediately)
- [x] Both: Updated nodes: 2s highlight pulse via CSS keyframe (`node-pulse` animation in `AnalysisNodeComponent`)
- [x] Both: After adding nodes: `fitView()` with 500ms delay via `FitViewEffect.svelte` + `fitViewSignal`

---

## PHASE 4 — User Interactions on Graph

### 4.1 Node Detail Panel (both frontends)
- [-] [React] `NodeDetailPanel.tsx` — slide-over, Escape to close
- [x] [Svelte] `NodeDetailPanel.svelte` — slide-over panel, Escape via `svelte:window`
- [x] Editable fields: label, content (textarea), score (feasibility only)
- [x] Save → `graphStore.updateNode()` + `sessionStore.saveGraph()`
- [x] Delete → `graphStore.deleteNode()` + close panel
- [x] Save/Delete → push system message to chatStore + persist to DB (via `addSystemMessage` in session page)

### 4.2 Graph Toolbar (both frontends)
- [-] [React] `GraphToolbar.tsx`
- [x] [Svelte] `GraphToolbar.svelte` — floating panel in GraphPanel
- [x] "Fit View" → `fitView()`
- [x] "Auto Layout" → re-run Dagre on current graph
- [x] "Add Node" → `AddNodeModal` with DimensionType selector + system message push
- [x] "Add Edge" → drag from node handles (SvelteFlow default); `onconnect` wired to persist edge to store + DB
- [x] "Delete Selected" → `deleteSelected()` in `GraphToolbar.svelte`; `ondelete` in `GraphPanel.svelte`

### 4.3 Drag and Reposition (both frontends)
- [x] `onNodeDragStop` → `graphStore.setNodePosition()` + mark `userPositioned: true`
- [x] Debounced graph save on drag stop

### 4.4 Graph → Chat Feedback Loop (both frontends)
- [x] Manual graph mutations → push `role: 'system'` message to chatStore AND persist to DB
- [x] Message format: `[User action: edited node "Benefits › Faster delivery"]`
- [x] System messages displayed in chat as italic muted text (MessageBubble handles `role === 'system'`)

### 4.5 Node Context Menu (both frontends)
- [-] [React] Right-click → Radix ContextMenu
- [x] [Svelte] Right-click node → context menu: "Edit", "Delete", "Ask Claude about this" (via `onnodecontextmenu` in `GraphPanel.svelte`)
- [x] Both: "Ask Claude" → pre-fills ChatInput: `Tell me more about: [node.label]`

---

## PHASE 5 — Polish and Production

### 5.1 Dashboard Page (both frontends)
- [x] Session cards: name, idea excerpt, model badge, relative time
- [x] Sort by `updated_at` desc
- [x] Paginated (20/page); "Load more" button shows remaining count
- [x] Delete button → confirmation toast with "Undo" within 5s (optimistic removal, actual delete on dismiss)
- [x] API key missing banner (yellow/warning)
- [x] Empty state

### 5.2 UI Polish (both frontends)
- [-] [React] `AppHeader.tsx`
- [x] [Svelte] `AppHeader.svelte` — logo, session name (double-click to rename), model badge
- [x] User logout button in dashboard header and `AppHeader.svelte`
- [x] Loading skeleton for session list cards on Dashboard
- [x] Loading skeleton for session workspace while session loads
- [x] Empty state in GraphPanel
- [x] Empty state in ChatPanel
- [x] Toast notifications (svelte-sonner)
- [x] Keyboard shortcuts: `Enter` / `Ctrl+Enter` to send in `ChatInput.svelte`; `Escape` to close NodeDetailPanel + context menu

### 5.3 Error Handling (both frontends)
- [-] [React] React `ErrorBoundary`
- [x] [Svelte] `<svelte:boundary>` wrapping workspace in `session/[id]/+page.svelte`
- [x] SSE error events → inline error in chat
- [x] 404/error page via `+error.svelte` at route root
- [x] Backend: FastAPI global exception handler
- [x] Session load 404/403 → redirect to Dashboard with toast

### 5.4 Security Hardening
- [x] `slowapi` integrated into app
- [x] Rate limits applied on all routes: `/auth/*` 5/15min, `/api/chat` 30/min, `/api/sessions/*` 60/min
- [x] Security headers middleware (X-Content-Type-Options, X-Frame-Options, HSTS in prod)
- [x] Middleware order: SecurityHeaders → CORS → routes
- [x] CORS `allow_origins` configurable via settings
- [x] Model allowlist in Pydantic validator
- [x] Never log decrypted API keys or JWT secrets

### 5.5 Testing (both frontends + backend)
- [x] All backend unit + integration tests (98 tests, 99% coverage)
- [-] [React] Vitest for graphStore, SSE parser
- [x] [Svelte] Vitest for `graphStore.applyGraphActions` — all 4 action types
- [x] [Svelte] Vitest for stores (chatStore), schemas (graph Zod), utilities (debounce, graphLayout)
- [x] [Svelte] Vitest for SSE parser in `chatService.ts` (8 tests — token, graph_action, error, ping, missing body, malformed JSON, Last-Event-ID)
- [-] [React] E2E Playwright
- [x] [Svelte] E2E Playwright: register → set API key → new analysis → graph → follow-up → edit node → settings → delete account

### 5.6 Docker — Production Builds
- [x] `infra/Dockerfile.backend` (multi-stage with development and production targets)
- [-] [React] `apps/web-react/Dockerfile`
- [x] [Svelte] `infra/Dockerfile.frontend` (multi-stage)
- [x] [Svelte] `infra/Dockerfile.frontend` uses `ARG PUBLIC_API_URL=""` + `ENV PUBLIC_API_URL=$PUBLIC_API_URL` — passed via `--build-arg` at deploy time; defaults to empty string

### 5.7 AWS Infrastructure — Terraform + EC2
> Primary deployment: EC2 t4g.small (API) + S3/CloudFront (frontend) + RDS, managed via Terraform.
> See `05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS.md` for full reference.

- [x] Bootstrap S3 + DynamoDB for Terraform state (`deploy/aws/terraform/bootstrap/main.tf`)
- [x] Implement all Terraform modules (networking, ecr, rds, secrets, iam, ec2, acm, s3, cloudfront) — `deploy/aws/terraform/modules/`
- [x] `terraform.tfvars`: EC2 t4g.small, RDS db.t3.micro (`terraform.tfvars.example`)
- [x] The EC2 instance runs the API container via Docker; the active frontend image is built into S3/CloudFront at deploy time — Terraform is frontend-agnostic
- [ ] `terraform plan && terraform apply` (manual — requires AWS credentials)
- [ ] Run `alembic upgrade head` via SSH on first deploy (manual — post-apply step)

### 5.7b Non-AWS Alternative — Railway + Neon + Vercel
> Near-free alternative (~$5/month vs ~$26/month for AWS). Choose this instead of §5.7 if cost is a constraint.
> Railway runs persistent containers — SSE works identically, no serverless concerns.
> See `05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT.md` for full execution details.

- [ ] Prerequisites: install Railway CLI (`npm i -g @railway/cli`), Vercel CLI, `pg_dump`/`pg_restore`; create Neon (free), Vercel (free), Railway (Hobby $5/month) accounts
- [x] **Step 1 — Neon (code):** SSL added to `backend/app/db/base.py` (auto-enabled when `neon.tech` in DATABASE_URL); manual: provision project, get pooled connection string, run Alembic migrations
- [ ] **Step 2 — Data migration** *(skip if fresh)*: dump RDS → restore to Neon
- [x] **Step 3 — Railway backend (code):** `backend/railway.toml` created; manual: `railway init`, set env vars, `railway up`, verify `/health`
- [x] **Step 4 — Vercel frontend (code):** `@sveltejs/adapter-vercel` installed, `svelte.config.js` updated (conditional on `ADAPTER=vercel`), `deploy/railway/README.md` added; manual: `vercel --prod`, set `PUBLIC_API_URL`
- [x] **Step 5 — CORS + cookie (code):** `samesite="lax"` in `backend/app/api/routes/auth.py`; manual: set `FRONTEND_URLS_RAW` Railway variable to Vercel URL
- [x] **Step 6 — CI/CD:** `deploy.yml` updated — disabled for now, triggers on `workflow_dispatch`; manual: add `RAILWAY_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_SVELTE` secrets
- [ ] **Step 7 — Smoke test:** health, register/login, cookie, SSE stream, graph actions, page refresh, CORS preflight
- [ ] **Step 8 — AWS teardown** *(only after smoke test passes)*: delete EC2 instance, RDS, S3 buckets, CloudFront distribution, ECR repos, Secrets Manager entries, security groups

### 5.8 CI/CD
- [x] `.github/workflows/ci.yaml` — backend lint + test, frontend type-check + test
- [x] `.github/workflows/deploy.yml` and `deploy-aws.yaml` exist (see `.github/workflows/`)

### 5.9 Documentation
- [x] Root `README.md`
- [x] `deploy/aws/README.md`: prerequisites, setup-infra → migrate → deploy sequence, secrets reference
- [x] `backend/app/prompts/README.md`: prompt design + changelog