# IdeaLens

An LLM-powered idea analysis tool. Describe any idea in natural language; Claude builds a live
knowledge graph — nodes for concepts, requirements, benefits, flaws, gaps, alternatives — while
you chat. Edit nodes directly, ask follow-up questions, and watch the graph evolve in real time.

Version: 1.0.0

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, `uv` |
| Frontend | SvelteKit 2, Svelte 5 (runes), TypeScript strict, TailwindCSS 4, Vite 7 |
| Graph | @xyflow/svelte 1.5.2 + Dagre auto-layout |
| Database | PostgreSQL 16, SQLAlchemy 2 async, asyncpg, Alembic |
| Auth | JWT access tokens + httpOnly refresh cookie, bcrypt |
| LLM | Anthropic SDK (user-supplied API key, encrypted at rest with Fernet) |
| Containerisation | Docker, Docker Compose |
| CI | GitHub Actions |
| Dev environment | VS Code devcontainer (Ubuntu 24.04) |

---

## Features

- **Streaming analysis** — Claude streams tokens and graph actions over SSE in real time
- **Live knowledge graph** — nodes auto-positioned with Dagre layout after each response; animated entry transitions
- **10 node types** — concept, requirement, benefit, drawback, gap, flaw, feasibility, alternative, question, root
- **Session persistence** — graph state, chat history (including system action messages), and model selection saved to PostgreSQL
- **Context window management** — older messages auto-summarised when session grows large
- **SSE reconnection** — `Last-Event-ID` replay on reconnect
- **User API key** — each user supplies their own Anthropic key; stored Fernet-encrypted, decrypted only in memory
- **Multi-model** — Haiku (fast), Sonnet (default), Opus (thorough)
- **Graph editing** — add nodes (9 types), delete nodes, auto-layout, drag to reposition; edits reflected in chat history
- **Node detail panel** — view/edit node content; "Ask Claude" pre-fills chat input; Escape to close
- **Settings** — profile, password, API key management, account deletion
- **Error boundaries** — `<svelte:boundary>` in the session workspace; `+error.svelte` for 404/500 pages

---

## Quick start (devcontainer)

```bash
# 1. Open in VS Code devcontainer (auto-installs all deps)

# 2. Start PostgreSQL (first time only; survives container rebuild)
sudo service postgresql start

# 3. Apply DB migrations
cd backend && uv run alembic upgrade head

# 4. Copy and fill in environment variables
cp .env.example .env
# Required: JWT_SECRET, API_KEY_ENCRYPTION_KEY, DATABASE_URL

# 5. Run backend + frontend in parallel
make dev
```

Backend on `:8000`, frontend on `:5173`.

---

## Environment variables

| Variable | Where | Notes |
|---|---|---|
| `DATABASE_URL` | backend | `postgresql+asyncpg://user:pass@host/db` |
| `JWT_SECRET` | backend | Min 32 chars. Generate: `openssl rand -hex 32` |
| `API_KEY_ENCRYPTION_KEY` | backend | Fernet key. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ENVIRONMENT` | backend | `development` (default) or `production` |
| `FRONTEND_URLS_RAW` | backend | Comma-separated allowed CORS origins. Default: `http://localhost:5173` |
| `CONTEXT_WINDOW_MAX_MESSAGES` | backend | Messages before summarisation kicks in. Default: `20` |
| `PUBLIC_API_URL` | frontend | Backend base URL. Default: `http://localhost:8000` |
| `ORIGIN` | frontend | Production only — required by adapter-node for CSRF. Set to the public frontend URL. |

---

## Commands

```bash
# Backend (from repo root)
make dev        # backend + frontend in parallel
make backend    # backend only (port 8000, hot reload)
make frontend   # frontend only (port 5173, hot reload)
make test       # pytest (quiet)

# Backend — from backend/
uv run pytest                          # all tests
uv run pytest tests/path/test.py::fn  # single test
uv run pytest --no-cov                # skip coverage
uv run alembic upgrade head            # apply migrations
uv run alembic revision --autogenerate -m "description"
ruff check .                          # lint
ruff format .                         # format

# Frontend — from frontend/
bun run dev           # dev server
bun run build         # production build
bun run check         # svelte-check + tsc
bun run test          # vitest (run once)
bun run test:coverage # with coverage report
bun run test:e2e      # Playwright E2E (backend must be running on :8000)
bun run test:e2e:ui   # Playwright with interactive UI

# Pre-commit
pre-commit run --all-files
```

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/         # auth, users, sessions, chat, models
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   └── config.py       # pydantic-settings Settings (get_settings lru_cache)
│   │   ├── db/
│   │   │   ├── models/         # User, RefreshToken, Session, Message
│   │   │   ├── base.py         # async engine + AsyncSessionLocal
│   │   │   └── session.py      # get_db dependency
│   │   ├── dependencies/
│   │   │   └── auth.py         # get_current_user
│   │   ├── prompts/
│   │   │   └── analysis_system.py  # Claude system prompt
│   │   ├── schemas/            # Pydantic schemas: auth, user, session, chat, graph
│   │   ├── services/           # auth_service, encryption_service, llm_service
│   │   └── main.py             # create_app() factory, middleware, lifespan
│   ├── alembic/                # Async Alembic config + migrations
│   ├── tests/                  # 98 tests, 99% coverage
│   │   ├── conftest.py         # NullPool per-test engine, SAVEPOINT isolation
│   │   ├── test_auth.py
│   │   ├── test_users.py
│   │   ├── test_sessions.py
│   │   ├── test_chat.py
│   │   ├── test_services.py
│   │   └── test_schemas.py
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +layout.ts              # SPA mode (ssr = false)
│   │   │   ├── login/                  # login page
│   │   │   ├── register/               # register page
│   │   │   └── (protected)/
│   │   │       ├── +layout.ts          # auth guard
│   │   │       ├── settings/           # profile, API key, password, delete account
│   │   │       └── (requires-api-key)/
│   │   │           ├── +layout.ts      # API key guard
│   │   │           ├── +page.svelte    # dashboard (session list + new analysis)
│   │   │           └── session/[id]/   # workspace: chat + graph
│   │   └── lib/
│   │       ├── components/
│   │       │   ├── chat/               # ChatPanel, ChatInput, MessageBubble, ModelSelector
│   │       │   ├── graph/              # GraphPanel, GraphToolbar, NodeDetailPanel, AnalysisNodeComponent
│   │       │   └── layout/             # AppHeader, SplitLayout
│   │       ├── schemas/
│   │       │   └── graph.ts            # Zod schemas for graph types and LLM actions
│   │       ├── services/               # authService, userService, sessionService, chatService
│   │       ├── stores/                 # authStore, chatStore, graphStore, sessionStore
│   │       └── utils/                  # graphLayout (Dagre), graphStyles, debounce
│   ├── e2e/                            # Playwright E2E tests
│   │   ├── auth.spec.ts                # 4 tests: register, login, logout, duplicate email
│   │   ├── user-journey.spec.ts        # 1 test: full happy-path (register → analysis → graph → delete)
│   │   ├── helpers.ts                  # shared utilities: buildSSEBody(), registerUser()
│   │   └── tsconfig.json
│   ├── playwright.config.ts            # Chromium only, webServer starts bun run dev
│   └── src/lib/example.test.ts         # 62 tests across stores, schemas, utils
│
├── deploy/
│   ├── Dockerfile.backend      # Multi-stage Python/uv image
│   ├── Dockerfile.frontend     # Multi-stage Bun builder + Node runner
│   ├── docker-compose.dev.yml  # PostgreSQL for local dev + test DB init
│   ├── docker-compose.yaml     # Full app (backend + frontend)
│   ├── aws/
│   │   ├── setup-infra.sh      # One-time: RDS, VPC connector, Secrets Manager
│   │   ├── deploy.sh           # ECR + App Runner (reads root .env)
│   │   └── README.md           # Full AWS setup procedure
│   ├── gcp/deploy.sh           # Artifact Registry + Cloud Run (placeholder)
│   └── azure/deploy.sh         # ACR + Container Apps (placeholder)
├── .github/workflows/          # ci.yaml + deploy-{aws,gcp,azure}.yaml
├── Makefile
└── docs/plan/                  # Architecture, todos, implementation plans
```

---

## Test coverage

```
Backend:  104 tests · 99% coverage  (requires PostgreSQL — see CLAUDE.md)
Frontend:   81 tests (stores, schemas, utilities, SSE parser)
E2E:         5 Playwright tests (auth flows + full user journey)
Deploy:      9 tests (syntax + required-variable enforcement)
```

Run backend coverage report (PostgreSQL must be running):

```bash
cd backend && uv run pytest
```

Run frontend unit tests:

```bash
cd frontend && bun run test
```

Run E2E tests (requires backend + frontend running):

```bash
# Terminal 1
make backend

# Terminal 2 — run tests (starts frontend dev server automatically)
cd frontend && bun run test:e2e
```

Run deploy script tests (no database required):

```bash
bash deploy/tests/test_deploy_scripts.sh
```

---

## Architecture notes

**Streaming:** `POST /api/chat` returns a `StreamingResponse`. A queue-based producer/consumer pattern runs the LLM call and a 15-second heartbeat ping concurrently. The frontend SSE parser handles `token`, `graph_action`, `ping`, `error`, and `done` events.

**Graph actions:** The LLM returns a structured `LLMResponse` with a `graph_actions` array. Each action is Pydantic-validated against a discriminated union (`add`, `update`, `delete`, `connect`). Actions are streamed as `graph_action` SSE events; the frontend applies them to the graphStore and re-runs Dagre layout on completion.

**Context management:** When `session.messages` exceeds `CONTEXT_WINDOW_MAX_MESSAGES`, the oldest messages are summarised with `claude-haiku-4-5` and stored in `session.context_summary`. Subsequent LLM calls inject the summary as a user/assistant context pair.

**API key security:** User Anthropic keys are encrypted with Fernet before DB storage. The raw key exists only in memory during the LLM call. Keys are validated against the Anthropic API on first save.

**Auth:** Short-lived JWT access tokens (15 min) + long-lived httpOnly refresh cookie (7 days). Refresh tokens are stored in the DB for revocation. The refresh cookie is scoped to `/auth` path to limit exposure.

---

## What's not yet built

See [`docs/plan/02_TODOS.md`](docs/plan/02_TODOS.md) for the full status. All major features are shipped as of v1.0.0. No blocking deferred items remain.

---

## Deployment

Four deployment paths are supported. See [`deploy/README.md`](deploy/README.md) and the per-provider guides for full instructions.

**Railway + Vercel + Neon (recommended easiest path)**

See [`deploy/railway/README.md`](deploy/railway/README.md) for step-by-step setup. No Docker required; the backend deploys directly from the repo via `backend/railway.toml`. The frontend deploys to Vercel using `@sveltejs/adapter-vercel`.

**AWS (Terraform — EC2 + S3 + CloudFront + RDS)**

```bash
# First time: provision infra with Terraform (see deploy/aws/README.md)
cd deploy/aws/terraform && terraform apply

# Subsequent deploys
bash deploy/aws/deploy.sh
```

**GCP Cloud Run**

```bash
bash deploy/gcp/deploy.sh
```

**Azure Container Apps**

```bash
bash deploy/azure/deploy.sh
```
