# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- **Backend**: FastAPI + Uvicorn, Python 3.12, managed with `uv`
- **Frontend**: SvelteKit 2 + Svelte 5, TypeScript strict, TailwindCSS 4, Vite 7
- **Infra**: Docker Compose, VS Code dev container (Ubuntu 24.04)

## Commands

```bash
# Development (from repo root)
make dev        # Run backend + frontend in parallel
make backend    # Backend only (port 8000, hot reload)
make frontend   # Frontend only (port 5173, hot reload)
make test       # Run pytest (quiet)

# Backend
uv sync --directory backend   # Install/sync Python deps
ruff check backend/           # Lint
ruff format backend/          # Format
ruff check --fix backend/     # Lint + auto-fix
pytest -q                     # Tests (run from backend/)
pytest tests/path/test_file.py::test_name  # Single test

# Frontend (run from frontend/)
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
main.py          # FastAPI app entry point, lifespan, global middleware
api/
  routes/        # Route handlers grouped by domain
  deps.py        # FastAPI dependency injection
core/
  config.py      # Settings (pydantic-settings)
  security.py    # Auth/JWT utilities
services/        # Business logic layer (called by routes)
models/          # SQLAlchemy ORM models
schemas/         # Pydantic request/response schemas
db/
  session.py     # Async DB session factory
  base.py        # Declarative base
tests/           # pytest tests
```

Routes call services; services own business logic and call models/db. Schemas are strictly input/output contracts — no model objects leak into API responses.

### Frontend (`frontend/src/`)

```
routes/           # File-based routing (+page.svelte, +layout.svelte, +page.ts)
lib/
  components/     # Reusable Svelte components
  stores/         # Svelte stores (shared state)
  api/            # Typed API client (fetch wrappers)
  index.ts        # Barrel export for lib/
app.d.ts          # Global TypeScript declarations
app.html          # HTML shell
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
- pytest coverage reports configured; run with `pytest --cov`.
