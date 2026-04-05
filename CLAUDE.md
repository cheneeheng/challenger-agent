# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- **Backend**: FastAPI + Uvicorn, Python 3.12, managed with `uv`
- **Frontend**: SvelteKit 2 + Svelte 5, TypeScript strict, TailwindCSS 4, Vite 7
- **Database**: PostgreSQL 16, SQLAlchemy 2 async, Alembic
- **Infra**: Docker Compose, VS Code dev container (Ubuntu 24.04)

## Environment Setup

PostgreSQL must be running before starting the backend or running tests:

```bash
sudo service postgresql start   # required in devcontainer — not auto-started
```

On first clone or after schema changes:

```bash
cd backend && uv run alembic upgrade head
```

## Commands

```bash
# Development (from repo root)
make dev        # Run backend + frontend in parallel
make backend    # Backend only (port 8000, hot reload)
make frontend   # Frontend only (port 5173, hot reload)
make test       # Run pytest (quiet)

# Backend (from backend/)
uv sync                                        # Install/sync Python deps
uv run pytest                                  # Tests with coverage
uv run pytest --no-cov                         # Tests without coverage
uv run pytest tests/path/test_file.py::test_name  # Single test
uv run alembic upgrade head                    # Apply DB migrations
uv run alembic revision --autogenerate -m "desc"  # Generate migration
ruff check .                                   # Lint
ruff format .                                  # Format
ruff check --fix .                             # Lint + auto-fix

# Frontend (from frontend/)
bun run dev       # Dev server
bun run build     # Production build
bun run check     # Type-check (svelte-check + tsc)
bun run preview   # Preview production build
bun run test      # Run vitest (unit tests)
bun run test:coverage  # With coverage report

# Pre-commit
pre-commit run --all-files
```

## Architecture

### Backend (`backend/app/`)

```
main.py               # FastAPI app entry point, lifespan, middleware
api/
  routes/             # auth, users, sessions, chat, models
dependencies/
  auth.py             # get_current_user dependency
core/
  config.py           # Settings (pydantic-settings) — list fields use _RAW suffix
services/             # Business logic layer (called by routes)
  auth_service.py
  encryption_service.py
  llm_service.py
prompts/
  analysis_system.py  # Claude system prompt
schemas/              # Pydantic request/response schemas: auth, user, session, chat, graph
db/
  models/             # User, RefreshToken, Session, Message
  session.py          # Async DB session factory (expire_on_commit=False)
  base.py             # Async engine + AsyncSessionLocal
tests/                # 98 tests, 99% coverage
```

Routes call services; services own business logic and call models/db. Schemas are strictly input/output contracts — no model objects leak into API responses.

### Frontend (`frontend/src/`)

```
routes/               # File-based routing (+page.svelte, +layout.svelte, +page.ts)
  (protected)/        # Auth-guarded routes; (requires-api-key)/ nested inside
lib/
  components/         # chat/, graph/, layout/ subdirectories
  stores/             # authStore, chatStore, graphStore, sessionStore
  services/           # authService, chatService, sessionService, userService
  schemas/            # graph.ts — Zod schemas for LLM graph actions
  utils/              # graphLayout.ts (Dagre), graphStyles.ts, debounce.ts
```

Svelte 5 runes syntax (`$props()`, `$state()`, `$derived()`, `{@render ...}`). TailwindCSS v4 — configured via Vite plugin, no `tailwind.config.js`.

### Ports

| Service  | Port |
|----------|------|
| Backend  | 8000 |
| Frontend | 5173 |

## Code Quality

- **Ruff** enforces backend lint + format (line length 79, double quotes). Config in `pyproject.toml` `[tool.ruff]`.
- **svelte-check** + **tsc** enforce frontend type safety.
- Pre-commit hooks run Ruff on `backend/` only.
- pytest coverage reports configured; run with `uv run pytest`.

## Gotchas

**Backend list settings use `_RAW` suffix in `.env`:**
`FRONTEND_URLS_RAW` and `ALLOWED_CLAUDE_MODELS_RAW` — exposed as properties without the suffix.
pydantic-settings v2 JSON-decodes list fields before validators run; the `str` field + `@property` pattern works around this.

**`@xyflow/svelte` v1.5.2 — events are props, not `on:` directives:**
Use `onnodedragstop`, `onnodeclick`, `onpaneclick`, `ondelete` as props on `<SvelteFlow>`.
`ondelete` receives `{nodes, edges}` — there are no separate `nodesdelete`/`edgesdelete` events.

**Svelte 5 runes mode — `afterUpdate` is removed:**
Use `$effect(() => { ... })` instead. Add `setTimeout(..., 0)` if DOM measurement is needed after paint.

**Test DB session must match production `AsyncSessionLocal`:**
`AsyncSession(..., expire_on_commit=False)` is required in test fixtures. Without it, `db.commit()` mid-request expires attributes and triggers `MissingGreenlet` errors in async route handlers.
