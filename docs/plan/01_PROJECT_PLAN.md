---
doc: 01_PROJECT_PLAN
status: ready
version: 1
created: 2026-04-18
scope: Goals, confirmed stack, user journey, feature set, phases, NFRs, out-of-scope, success criteria
relates_to:
  - 02_TODOS
  - 03_ARCHITECTURE
  - 04_LIBRARIES_AND_FRAMEWORKS
  - 05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS
  - 06_BACKEND_IMPLEMENTATION
  - 07_FRONTEND_IMPLEMENTATION
  - 07_FRONTEND_IMPLEMENTATION_SVELTE
  - 08_LLM_AND_PROMPT
---

# PROJECT PLAN — IdeaLens

**Stack:** React 19 + Vite · SvelteKit · TypeScript · Python 3.12 · FastAPI · PostgreSQL · SQLAlchemy 2.x async · Anthropic SDK · AWS

> LLM-powered idea analysis and feasibility visualization app

---

## 1. Project Overview

**App Name:** IdeaLens
**Type:** Full-stack web application
**Purpose:** Allow users to submit any idea or topic, have an LLM deeply analyze it across multiple structured dimensions, and visualize the resulting analysis as an interactive node-based graph. Both the chat and the graph are live and collaborative — the LLM can modify the graph in real time as the conversation evolves.

**Repo structure:** Monorepo with **two frontend implementations** built side-by-side against the same backend, for direct framework comparison. Only one frontend is deployed at a time — the choice is made at deploy time via a `DEPLOY_FRONTEND` variable.

**Confirmed Stack:**
- Frontend A: React + Vite (TypeScript) — `apps/web-react`
- Frontend B: SvelteKit (TypeScript) — `apps/web-svelte`
- Backend: Python + FastAPI — `apps/api` (shared by both frontends)
- LLM: Anthropic SDK — model selectable by user; API key provided by user
- Validation: Pydantic v2 + pydantic-settings (backend), Zod (both frontends)
- Graph: `@xyflow/react` (React version) / `@xyflow/svelte` (SvelteKit version)
- Database: PostgreSQL via SQLAlchemy 2.x async + Alembic
- Infrastructure: Terraform → AWS (v1), GCP support in v2
- DNS: Free tier (e.g. Afraid.org) for v1
- Email / Password reset: Deferred to v2
- Google OAuth: Deferred to v2

**Frontend implementation references:**
- React version: `07_FRONTEND_IMPLEMENTATION.md`
- SvelteKit version: `07_FRONTEND_IMPLEMENTATION_SVELTE.md`

---

## 2. Core User Journey

Both frontends implement an identical user journey. The backend API and DB are shared.

```
[Login / Register Page]
        ↓
[Dashboard — Session List]
  - Banner shown if API key not set
  - "New Analysis" button
        ↓
[User sets Anthropic API Key in Settings (one-time, first visit)]
        ↓
["New Analysis" modal: textarea for idea + model selector]
        ↓
[POST /api/sessions → session created with root node in DB]
        ↓
[Navigate to /session/:id → auto-send idea as first message]
        ↓
[Workspace — Split View]
  Left Panel: Chat Interface  |  Right Panel: Node Graph Visualization
        ↓
[LLM streams analysis → graph populates with nodes in real time]
        ↓
[User continues chatting → graph updates dynamically]
        ↓
[User can manually drag, edit, add, remove nodes]
        ↓
[Session auto-saved and revisitable from Dashboard]
```

---

## 3. Feature Set

All features below are implemented in both frontends. Framework-specific implementation
details are noted where the mechanism differs between React and SvelteKit.

### 3.1 Authentication (v1 — email + password only)
- Email + password registration and login
- JWT-based session management (15-min access token + 7-day httpOnly refresh token cookie)
- Protected routes — redirect to `/login` if unauthenticated
  - React: `ProtectedRoute` component wrapper
  - SvelteKit: `+layout.ts` `load()` function with `redirect()`
- No password reset in v1
- Google OAuth deferred to v2

### 3.2 User Settings (`/settings`)
- **Anthropic API Key** — stored Fernet-encrypted in DB; `has_api_key: bool` is the only value ever returned to the frontend; validated against Anthropic before saving
- **Display Name** — editable
- **Change Password** — requires current password confirmation
- **Delete Account** — requires password confirmation; cascades all data
- API key missing banner shown on Dashboard when `has_api_key === false`
- Routes requiring API key protected by guard:
  - React: `ApiKeyGuard` component
  - SvelteKit: nested route group `+layout.ts`

### 3.3 Chat Interface (Left Panel)
- SSE streaming LLM responses with token-by-token display
- Message history per session (user, assistant, system roles)
- System messages (graph feedback) displayed differently — italic, muted, no avatar
- Model selector dropdown in chat panel header
- Input disabled while `isStreaming === true` — no concurrent messages possible

### 3.4 New Analysis Flow
1. "New Analysis" button on Dashboard → `NewAnalysisModal`
2. Modal: idea textarea + model selector + Submit
3. `POST /api/sessions` → creates session with root node pre-populated in `graph_state`
4. Navigate to `/session/:id`
5. Session page on mount: if `messages.length === 0`, auto-send idea as first message
   - React: guarded by `useRef` to prevent double-fire in StrictMode
   - SvelteKit: guarded by a module-scoped `let` boolean + reactive `$:` block
6. Session always exists in DB before any message is sent — no race condition

### 3.5 LLM Model Selection
Per-session user choice, stored in DB, passed to Anthropic SDK on every request.

| Model | Speed | Quality | Default |
|---|---|---|---|
| `claude-haiku-4-5` | Fastest | Good | No |
| `claude-sonnet-4-6` | Balanced | High | **Yes** |
| `claude-opus-4-6` | Slowest | Highest | No |

Backend validates model string against `ALLOWED_CLAUDE_MODELS` on every chat request.

### 3.6 LLM Analysis Dimensions
9 dimensions, each maps to a node type and visual style:

| Dimension | Node Type | Description |
|---|---|---|
| Core Concept | `concept` | What the idea is fundamentally about |
| Requirements | `requirement` | Resources, skills, time, money needed |
| Gaps | `gap` | What is missing or unknown |
| Benefits | `benefit` | Positive outcomes |
| Drawbacks | `drawback` | Risks and negatives |
| Feasibility | `feasibility` | Score 0–10 + reasoning |
| Flaws | `flaw` | Logical inconsistencies |
| Alternatives | `alternative` | Other approaches |
| Open Questions | `question` | Things needing further research |

Plus `root` — the central idea node, created on session creation, never modified by LLM.

### 3.7 Context Window Management
- Keep last 20 messages verbatim
- Messages beyond 20 summarized once using `claude-haiku-4-5`
- Summary stored in `session.context_summary`; reused on every subsequent request
- Full graph state always included regardless of message count
- Threshold configurable via `CONTEXT_WINDOW_MAX_MESSAGES` env var

### 3.8 Node Graph Visualization (Right Panel)
- Interactive node graph with custom node components, color-coded per dimension type
  - React: `@xyflow/react` (React Flow)
  - SvelteKit: `@xyflow/svelte` (Svelte Flow — same API family)
- Initial layout via Dagre (directed graph auto-layout) — identical in both versions
- Incremental position assignment for nodes added after initial layout
- User interactions: drag, click to edit, add node/edge, delete, context menu
- LLM interactions: add, update, delete, connect via validated graph actions
- Minimap, zoom, pan, fit-view controls
- Resizable split panel (drag handle; default 40%/60%)
  - React: `react-resizable-panels`
  - SvelteKit: `svelte-splitpanes`

### 3.9 Dashboard Page
- Session list: cards showing session name, idea excerpt, model badge, last-updated timestamp
- Cards sorted by `updated_at` descending
- Click card → navigate to `/session/:id`
- Hover card → show Delete button
- "New Analysis" button (top right)
- API key missing banner (top, dismissible for session only, reappears on refresh)
- Empty state: "No analyses yet. Start your first one →"

### 3.10 Session Management
- Sessions auto-saved to PostgreSQL via debounced graph persist (1 second)
- Session name defaults to first 60 chars of idea; editable inline in AppHeader
- Rename, delete, continue any session from Dashboard

### 3.11 Account Management
- `DELETE /api/users/me` with password confirmation → cascades sessions, messages, refresh tokens
- Frontend: "Danger Zone" section in `/settings` with confirmation modal

### 3.12 Infrastructure
- Dockerized; Terraform-managed AWS (ECS Fargate + RDS + ALB + ACM)
- Both frontends available in local dev (React :3000, SvelteKit :3001); only one deployed to production at a time
- Active frontend for deployment selected via `DEPLOY_FRONTEND=react|svelte` in the deploy workflow
- HTTPS enforced; secrets in AWS Secrets Manager
- GitHub Actions CI/CD — backend tested once; each frontend tested independently; only the selected frontend image deployed

---

## 4. Phases

Phases 1–2 (backend) and Phase 5 (production) are shared. Phases 3–4 (visualization and
graph interactions) are implemented twice — once per frontend.

### Phase 1 — Foundation
- Monorepo scaffolding with `apps/web-react`, `apps/web-svelte`, `apps/api`
- docker-compose with both frontend services on separate ports
- FastAPI app factory, pydantic-settings, CORS, middleware order
- SQLAlchemy async engine, Alembic (async env.py), migrations, seed script
- Auth routes + refresh token cookie spec
- User settings routes (API key, name, password, delete account)
- Both frontend auth pages, stores, Axios interceptors
- Settings page, auth guards, ProtectedRoute equivalents
- Basic split-panel workspace layout in both frontends

### Phase 2 — Analysis Engine
- Pydantic graph schemas (with NodePayload separate from AnalysisNode)
- LLM service: build_messages, stream_response, parse_llm_response, summarize
- SSE streaming endpoint with heartbeat, error handling, reconnection
- Context window management
- Session + message CRUD with pagination
- Graph state payload guard
- conftest.py fixtures and test suite

### Phase 3 — Visualization (both frontends in parallel)
- React Flow setup (React) / Svelte Flow setup (SvelteKit) — controlled pattern
- Dagre auto-layout on initial render — shared `graphLayout.ts` logic
- Incremental position assignment
- Custom node components per dimension type
- Animated graph updates

### Phase 4 — User Interactions on Graph (both frontends in parallel)
- Node detail slide-over panel
- Graph toolbar (add node, add edge, delete selected, fit view, auto layout)
- Drag and reposition with debounced save
- Graph → chat feedback loop (system messages)
- Right-click context menu

### Phase 5 — Polish and Production
- Dashboard page (session cards, empty state, API key banner)
- Error boundaries / error handling, loading skeletons, empty states
- Toast notifications, keyboard shortcuts
- Security hardening
- Docker production Dockerfiles (one per frontend + api); deploy selects one frontend
- Terraform bootstrap + apply
- GitHub Actions CI + CD

---

## 5. Non-Functional Requirements

| Requirement | Target |
|---|---|
| LLM first token latency | < 2s |
| Auth token expiry | 15-min access / 7-day refresh |
| Uptime | 99.5%+ |
| HTTPS | Enforced |
| Data isolation | Users see only their own sessions |
| Input validation | Pydantic v2 + Zod on every boundary |
| API key security | Encrypted at rest; never returned in plaintext |
| Context limit | Last 20 messages; older summarized |
| Concurrent messages | Blocked by `isStreaming` guard |
| Session list | Paginated — 20 per page |
| Frontend parity | Both frontends expose identical functionality |

---

## 6. Out of Scope (v1)
- Password reset / email
- Google OAuth
- GCP deployment
- Mobile app
- Multiplayer / shared sessions
- Export (PDF, image, markdown)
- Billing
- Running both frontends simultaneously in production

---

## 7. Deferred to v2
- Password reset (Resend)
- Google OAuth
- GCP deployment (second Terraform workspace)
- Export features
- Usage/token dashboard per session

---

## 8. Success Criteria
- User registers, sets API key, creates analysis, sees full graph in real time — verified in both frontends
- Chat updates graph via SSE; manual edits feed back into LLM context
- Long sessions handled gracefully via context summarization
- Sessions persist; dashboard shows history
- Account management works (settings, delete)
- Both frontends run in local dev (React on :3000, SvelteKit on :3001); one is selected and deployed to AWS
- Live on public internet over HTTPS on AWS