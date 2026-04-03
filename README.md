# {{ project_name }}

> Template version: 0.2.2

A production-ready project template for building full-stack applications with
FastAPI and SvelteKit.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, `uv` |
| Frontend | SvelteKit 2, Svelte 5, TypeScript strict, TailwindCSS 4, Vite 7 |
| Runtime | Node.js 24 (via `adapter-node`) |
| Containerisation | Docker, Docker Compose |
| CI | GitHub Actions |
| Dev environment | VS Code devcontainer (Ubuntu 24.04) |

---

## Using this template

### 1. Create your repository

On GitHub, click **Use this template → Create a new repository**.

Or clone manually:

```bash
git clone https://github.com/your-org/template-fastapi-sveltekit my-project
cd my-project
git remote set-url origin https://github.com/your-org/my-project
```

### 2. Replace placeholders

Search for `{{ }}` tokens and replace them:

| Token | File | Replace with |
|---|---|---|
| `{{ project_name }}` | `README.md` | Your project name |
| `{{ author_name }}` | `backend/pyproject.toml` | Your name |
| `author@example.com` | `backend/pyproject.toml` | Your actual email |

Also rename the packages themselves:

```bash
# backend/pyproject.toml
name = "my-project"            # was "backend"

# frontend/package.json
"name": "my-project"           # was "frontend"
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY
openssl rand -hex 32           # generates a secure SECRET_KEY
```

### 4. Open in devcontainer

Open the repo in VS Code and click **Reopen in Container** when prompted.

The devcontainer will automatically:
- Install Python 3.12 + `uv` and sync backend dependencies
- Install Node.js 24 + Bun and install frontend dependencies
- Install Claude Code CLI globally
- Configure all VS Code extensions (Ruff, Svelte, Pylance, etc.)

### 5. Start developing

```bash
make dev        # backend on :8000 + frontend on :5173 (parallel)
make backend    # backend only
make frontend   # frontend only
```

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/         # Route handlers — one file per domain
│   │   │   └── deps.py         # FastAPI dependency injection
│   │   ├── core/
│   │   │   ├── config.py       # Settings via pydantic-settings (.env)
│   │   │   └── security.py     # Auth/JWT helpers (add when needed)
│   │   ├── services/           # Business logic — called by routes
│   │   ├── models/             # SQLAlchemy ORM models (add when needed)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── db/
│   │   │   ├── session.py      # Async DB session factory (add when needed)
│   │   │   └── base.py         # Declarative base (add when needed)
│   │   └── main.py             # FastAPI app, middleware, lifespan
│   ├── tests/
│   │   ├── conftest.py         # pytest fixtures (TestClient)
│   │   └── test_main.py        # Health endpoint smoke test
│   └── pyproject.toml          # Dependencies, Ruff, pytest config
│
├── frontend/
│   ├── src/
│   │   ├── routes/             # File-based routing (+page.svelte, +layout.svelte)
│   │   ├── lib/
│   │   │   ├── api/            # Typed fetch wrappers for the backend
│   │   │   ├── components/     # Reusable Svelte components
│   │   │   └── stores/         # Svelte stores (shared state)
│   │   └── app.d.ts            # Global TypeScript declarations
│   ├── package.json
│   ├── svelte.config.js        # adapter-node for Docker/Node deployments
│   └── vite.config.ts          # Vite + Tailwind + vitest config
│
├── infra/
│   ├── docker-compose.yaml     # Production container orchestration
│   ├── Dockerfile.backend      # Multi-layer Python/uv image
│   └── Dockerfile.frontend     # Multi-stage Bun builder + Node runner
│
├── deploy/
│   ├── README.md               # Deployment guide
│   ├── aws/deploy.sh           # ECR + App Runner
│   ├── gcp/deploy.sh           # Artifact Registry + Cloud Run
│   └── azure/deploy.sh         # ACR + Container Apps
│
├── .devcontainer/              # VS Code devcontainer (Ubuntu 24.04)
├── .github/workflows/          # CI (ci.yaml) + deploy per provider
├── .env.example                # Environment variable reference
├── MAINTENANCE.md              # What to update regularly
└── Makefile                    # dev / backend / frontend / test
```

---

## Development

### Running tests

```bash
# Backend (from repo root)
make test

# Backend with coverage
cd backend && pytest --cov

# Frontend
cd frontend && bun run test
cd frontend && bun run test:coverage
```

### Code quality

```bash
# Backend lint + format
ruff check backend/
ruff format backend/
ruff check --fix backend/

# Frontend type-check
cd frontend && bun run check

# Run all pre-commit hooks
pre-commit run --all-files
```

### Adding a backend route

1. Create `backend/app/api/routes/my_domain.py`
2. Define a router and handlers — routes call services, not models directly
3. Register the router in `backend/app/main.py`

```python
# backend/app/api/routes/items.py
from fastapi import APIRouter

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
def list_items():
    return []
```

```python
# backend/app/main.py
from app.api.routes import items
app.include_router(items.router)
```

### Adding a frontend page

Create `frontend/src/routes/my-page/+page.svelte`. SvelteKit uses file-based routing.

Use `$props()`, `$state()`, `$derived()` — this template uses **Svelte 5 runes** syntax throughout.

### Adding environment variables

1. Add to `.env.example` with a comment explaining the value
2. Add to `backend/app/core/config.py` (`Settings` class) for backend vars
3. For frontend public vars, prefix with `PUBLIC_` — SvelteKit exposes these automatically

---

## Docker

### Build and run locally

```bash
cp .env.example .env    # fill in values first

cd infra
docker compose up --build
```

Backend serves on `:8000`, frontend on `:3000` (production build via Node). During local development with `make dev`, the frontend runs on `:5173` via the Vite dev server instead.

### Production images

Both Dockerfiles are production-ready:

- **`Dockerfile.backend`** — uses `uv` for fast, reproducible installs; installs deps before copying source for layer caching
- **`Dockerfile.frontend`** — multi-stage: Bun builder → slim Node runner; only the compiled `build/` output is in the final image

---

## Deployment

See [`deploy/README.md`](deploy/README.md) for full instructions.

```bash
export APP_NAME=myapp

# GCP Cloud Run
export GCP_PROJECT=my-gcp-project
bash deploy/gcp/deploy.sh

# AWS App Runner
export AWS_REGION=us-east-1
bash deploy/aws/deploy.sh

# Azure Container Apps
export RESOURCE_GROUP=myapp-rg
bash deploy/azure/deploy.sh
```

GitHub Actions workflows for each provider live in `.github/workflows/deploy-*.yaml` and are triggered manually via `workflow_dispatch`. Change the trigger to `push: branches: [main]` to enable auto-deploy on merge.

---

## Configuration reference

| Variable | Service | Default | Notes |
|---|---|---|---|
| `APP_ENV` | backend | `development` | Set to `production` in prod |
| `SECRET_KEY` | backend | `changeme` | Generate: `openssl rand -hex 32` |
| `CORS_ORIGINS` | backend | `http://localhost:5173` | Comma-separated list |
| `DATABASE_URL` | backend | — | Add when using a DB |
| `ORIGIN` | frontend | — | Required by adapter-node in production |
| `PUBLIC_API_BASE_URL` | frontend | — | Full URL of the backend |

---

## Maintenance

See [`MAINTENANCE.md`](MAINTENANCE.md) for a checklist of things to update periodically:
Python version, backend/frontend dependency upgrades, pre-commit hook versions, Node version, and GitHub Actions action pins.
