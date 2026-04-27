---
doc: 05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT
status: ready
version: 1
created: 2026-04-18
scope: Non-AWS deployment alternative — Railway (backend) + Neon (PostgreSQL) + Vercel (frontend); near-free, no Terraform
relates_to:
  - 02_TODOS
  - 05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS
---
# INFRASTRUCTURE & DEPLOYMENT — Non-AWS Alternative (Railway + Neon + Vercel)
**Stack:** Python 3.12 · FastAPI · Docker · Railway · Neon PostgreSQL · Vercel · GitHub Actions

> Non-AWS deployment option using a near-free stack:
> **Railway** (backend) · **Neon** (PostgreSQL) · **Vercel** (frontend)
>
> Estimated cost: ~$5/month (Railway Hobby). Neon and Vercel have generous free tiers.
> Zero application logic changes required. All changes are config and infra.

---


## 1. Architecture Comparison

### Before (AWS App Runner + RDS)

```
Internet → App Runner (frontend :3000)
         → App Runner (backend :8000) → VPC Connector → RDS PostgreSQL (private)

Secrets:  AWS Secrets Manager
Images:   ECR
Cost:     €140–€170/month
```

### After (Railway + Neon + Vercel)

```
Internet → Vercel (frontend — global CDN, HTTPS)
         → Railway (backend — persistent container, HTTPS) → Neon (PostgreSQL, pooled)

Secrets:  Railway env vars + Vercel env vars
Images:   Railway internal registry (no ECR)
Cost:     ~$5/month (Railway Hobby) + €0 Neon + €0 Vercel
```

### What does NOT change

- All application code (FastAPI, SvelteKit) — untouched
- Database schema — identical PostgreSQL; Alembic migrations run as-is
- Auth flow (JWT + httpOnly cookie) — works across origins with one config tweak
- SSE streaming — Railway runs a persistent container, no cold-start concerns
- `deploy/Dockerfile.backend` — reused by Railway directly

---

## 2. Prerequisites

Install the following CLIs before starting:

```bash
# Railway CLI
npm install -g @railway/cli
railway login

# Vercel CLI
npm install -g vercel
vercel login

# pg_dump / pg_restore (for data migration)
# macOS:  brew install postgresql
# Ubuntu: sudo apt install postgresql-client
```

You also need:
- A [Neon](https://neon.tech) account (free, no credit card required)
- A [Vercel](https://vercel.com) account (free)
- A [Railway](https://railway.app) account — Hobby plan at $5/month includes $5 of usage credit, which covers a small persistent backend comfortably

---

## 3. Step 1 — Provision Neon (Database)

### 3.1 Create a project

1. Log in to [console.neon.tech](https://console.neon.tech)
2. Click **New Project** → name it `idealens` → select the region closest to your Railway deployment → **Create**
3. Neon creates a default database named `neondb` and a `main` branch automatically

### 3.2 Get the connection string

In the Neon dashboard go to **Connection Details**. Select:
- **Connection string** tab
- Pooler: **Enabled** (Neon's built-in PgBouncer — important for connection reuse)
- Copy the full string

It looks like:
```
postgresql://idealens_owner:<password>@ep-<hash>-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
```

### 3.3 Convert for asyncpg

SQLAlchemy's `asyncpg` driver requires the `postgresql+asyncpg://` prefix. Strip `?sslmode=require` — SSL is configured in the engine instead:

```
# From Neon dashboard:
postgresql://idealens_owner:<pw>@ep-<hash>-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require

# For DATABASE_URL (asyncpg):
postgresql+asyncpg://idealens_owner:<pw>@ep-<hash>-pooler.us-east-2.aws.neon.tech/neondb
```

Save this — it becomes `DATABASE_URL` everywhere below.

### 3.4 Enable SSL in the SQLAlchemy engine

Neon requires SSL. Add `ssl=True` to the engine connect args in `backend/app/db/base.py`:

```python
# backend/app/db/base.py
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings

settings = get_settings()

connect_args = {}
if "neon.tech" in settings.DATABASE_URL:
    connect_args["ssl"] = True

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    connect_args=connect_args,
)
```

> **Alternative:** Append `?ssl=require` to the `DATABASE_URL` string — asyncpg honours it.
> Either approach works; the `connect_args` approach avoids URL parsing edge cases.

### 3.5 Run Alembic migrations against Neon

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://idealens_owner:<pw>@ep-<hash>-pooler.us-east-2.aws.neon.tech/neondb" \
  uv run alembic upgrade head
```

All migration steps should complete without errors.

---

## 4. Step 2 — Migrate Data from RDS

Skip this step if you have no production data to carry over (fresh deployment).

### 4.1 Make RDS temporarily publicly accessible

RDS is private by default. To dump it, either:

**Option A — Temporarily enable public access (simplest):**
```bash
aws rds modify-db-instance \
  --db-instance-identifier idealens-postgres \
  --publicly-accessible \
  --apply-immediately

# Wait ~2 minutes, then get the endpoint
aws rds describe-db-instances \
  --db-instance-identifier idealens-postgres \
  --query "DBInstances[0].Endpoint.Address" \
  --output text
```

**Option B — Use an EC2 bastion or AWS CloudShell in the same VPC** (no public exposure needed).

### 4.2 Dump from RDS

```bash
pg_dump \
  --no-owner \
  --no-acl \
  --format=custom \
  --host=<rds-endpoint> \
  --port=5432 \
  --username=idealens \
  --dbname=idealens \
  --file=idealens_backup.dump
```

### 4.3 Restore to Neon

```bash
pg_restore \
  --no-owner \
  --no-acl \
  --host=ep-<hash>-pooler.us-east-2.aws.neon.tech \
  --port=5432 \
  --username=idealens_owner \
  --dbname=neondb \
  --verbose \
  idealens_backup.dump
```

### 4.4 Disable public RDS access again (if you used Option A)

```bash
aws rds modify-db-instance \
  --db-instance-identifier idealens-postgres \
  --no-publicly-accessible \
  --apply-immediately
```

---

## 5. Step 3 — Deploy Backend to Railway

### 5.1 Create a Railway project

```bash
cd backend
railway init   # creates a new project; name it "idealens"
```

Railway auto-detects `deploy/Dockerfile.backend`. If it doesn't pick it up automatically, point to it via `railway.toml` (see §5.2).

### 5.2 Configure `railway.toml`

Create `backend/railway.toml`:

```toml
[build]
  dockerfilePath = "../deploy/Dockerfile.backend"
  dockerContext = "."
  target = "production"

[deploy]
  startCommand = "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"
  healthcheckPath = "/health"
  healthcheckTimeout = 30
  restartPolicyType = "on_failure"
```

> Railway injects a `PORT` env var automatically. The explicit `--port 8000` above keeps the port predictable. Alternatively, remove it and configure uvicorn to read `$PORT`.

### 5.3 Set environment variables

In the Railway dashboard → your service → **Variables**, add:

| Variable | Value |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...neon.tech/neondb` |
| `JWT_SECRET` | *(see note below)* |
| `API_KEY_ENCRYPTION_KEY` | *(see note below)* |
| `FRONTEND_URLS` | *(set after Vercel deploy — see §7)* |

> **If migrating from AWS:** use the **same** `JWT_SECRET` and `API_KEY_ENCRYPTION_KEY` to preserve existing user sessions and encrypted API keys. Retrieve them:
> ```bash
> aws secretsmanager get-secret-value --secret-id idealens/JWT_SECRET --query SecretString --output text
> aws secretsmanager get-secret-value --secret-id idealens/API_KEY_ENCRYPTION_KEY --query SecretString --output text
> ```
>
> If starting fresh:
> ```bash
> openssl rand -hex 32                                                                        # JWT_SECRET
> python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # API_KEY_ENCRYPTION_KEY
> ```

### 5.4 Deploy

```bash
railway up
```

Railway builds the Docker image remotely from `deploy/Dockerfile.backend` and deploys it as a persistent container. No ECR, no local image push required.

### 5.5 Verify

```bash
railway logs
# Confirm uvicorn started and DB connected
```

Your backend URL is shown in the Railway dashboard (e.g. `https://idealens-production.up.railway.app`). Note this — you need it for the frontend and CORS config.

```bash
curl https://idealens-production.up.railway.app/health
# Expected: {"status":"ok","environment":"production"}
```

---

## 6. Step 4 — Deploy Frontend to Vercel

Vercel deploys from your Git repository. No Dockerfile involved — Vercel runs the build natively.

### 6.1 SvelteKit frontend

Switch from `adapter-node` to `adapter-vercel`:

```bash
cd frontend
npm install --save-dev @sveltejs/adapter-vercel
```

Update `frontend/svelte.config.js`:

```javascript
import adapter from '@sveltejs/adapter-vercel'
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
  },
}
```

Deploy:

```bash
vercel --prod
```

Set the environment variable:

```bash
vercel env add PUBLIC_API_URL production
# Enter value: https://idealens-production.up.railway.app
```

> **Why `PUBLIC_API_URL` must be set explicitly:** the original production config uses an empty string (same-origin via nginx proxy). On Vercel the frontend and backend are on different origins, so the full Railway URL must be provided. See §7 for the corresponding CORS config.

> **`adapter-vercel` vs `adapter-node`:** Since `ssr = false` is set globally, all routes are client-side rendered. The Vercel adapter acts effectively as a static host — no SSR or serverless function concerns apply.

### 6.2 Note the frontend URL

After deployment Vercel assigns a URL like `https://idealens-<hash>.vercel.app`. Set a production alias in the Vercel dashboard for a stable URL (e.g. `idealens.vercel.app`).

Note this URL — needed for the CORS config in §7.

---

## 7. Step 5 — CORS & Cookie Configuration

This is the most important config change. The frontend (`*.vercel.app`) and backend (`*.railway.app`) are now on different origins.

### 7.1 Update `FRONTEND_URLS` on the backend

In the Railway dashboard → Variables, add:

```
FRONTEND_URLS = https://idealens.vercel.app
```

For multiple origins (e.g. both a stable alias and the hash URL):

```
FRONTEND_URLS = https://idealens.vercel.app,https://idealens-abc123.vercel.app
```

### 7.2 Verify the backend CORS middleware

In `backend/app/main.py`, confirm the CORS middleware reads from settings:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_URLS,   # list[str]
    allow_credentials=True,                  # required for httpOnly cookie
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In `backend/app/core/config.py`, confirm `FRONTEND_URLS` parses a comma-separated string into a list:

```python
class Settings(BaseSettings):
    FRONTEND_URLS: list[str] = []

    @field_validator("FRONTEND_URLS", mode="before")
    @classmethod
    def parse_frontend_urls(cls, v):
        if isinstance(v, str):
            return [u.strip() for u in v.split(",") if u.strip()]
        return v
```

### 7.3 Update cookie `SameSite` to `lax`

The current cookie spec uses `samesite="strict"`, which silently blocks cookies on cross-origin requests. Change to `lax` in all `set_cookie` calls in `backend/app/api/routes/auth.py`:

```python
response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,
    samesite="lax",      # changed from "strict"
    path="/auth",
    max_age=604800,
    secure=True,
)
```

> `lax` allows cookies on top-level navigations while blocking third-party contexts — the correct setting for a frontend on `vercel.app` calling an API on `railway.app`.

### 7.4 Frontend API base URL

`frontend/src/lib/config.ts` already reads from `PUBLIC_API_URL` — no code change needed:

```typescript
import { PUBLIC_API_URL } from '$env/static/public'
export const API_BASE_URL: string = PUBLIC_API_URL ?? ''
```

The Vercel env var set in §6.1 provides the Railway URL at build time.

---

## 8. Step 6 — Update GitHub Actions CI/CD

### 8.1 `ci.yaml` — no changes needed

The existing CI pipeline runs without any AWS or Railway dependencies. Keep it as-is.

### 8.2 New `deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    name: Deploy backend → Railway
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli

      - name: Deploy to Railway
        run: railway up --service idealens-backend --detach
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

  deploy-frontend:
    name: Deploy frontend → Vercel
    runs-on: ubuntu-latest
    needs: deploy-backend
    steps:
      - uses: actions/checkout@v4

      - name: Install Vercel CLI
        run: npm install -g vercel

      - name: Deploy frontend
        run: |
          vercel deploy \
            --prod \
            --yes \
            --cwd frontend \
            --token ${{ secrets.VERCEL_TOKEN }}
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID_SVELTE }}
```

### 8.3 Required GitHub Secrets

| Secret | How to get |
|--------|-----------|
| `RAILWAY_TOKEN` | Railway dashboard → Account → Tokens → **New Token** |
| `VERCEL_TOKEN` | Vercel dashboard → Account → Tokens |
| `VERCEL_ORG_ID` | `vercel whoami` or Vercel dashboard → Settings |
| `VERCEL_PROJECT_ID_SVELTE` | `.vercel/project.json` after first deploy in `frontend/` |

**Variables** (Settings → Variables → Actions):

| Variable | Value |
|----------|-------|
| `DEPLOY_FRONTEND` | `svelte` (or `react` if React is also deployed) |

---

## 9. Step 7 — Smoke Test Checklist

Run through these manually after the first deploy before tearing down AWS.

```
□ GET  https://idealens-production.up.railway.app/health  → {"status":"ok","environment":"production"}
□ POST /auth/register                                      → 201, access token returned
□ POST /auth/login                                         → 200, refresh_token cookie set as httpOnly
□ GET  /api/users/me                                       → 200, user object
□ POST /api/users/me/api-key                               → 200 (use a valid Anthropic key)
□ POST /api/sessions                                       → 201, session with root node
□ POST /api/chat                                           → SSE stream, tokens arrive, graph_action events fire
□ Frontend loads at Vercel URL                             → login page renders
□ Full flow: register → set API key → new analysis → graph appears in real time
□ Refresh page on /session/:id                             → session restores correctly
□ Dashboard shows session list
□ CORS preflight (OPTIONS) returns 200 with correct Access-Control-Allow-Origin
□ No CORS errors in browser DevTools console
```

To test CORS from the browser DevTools console:

```javascript
fetch('https://idealens-production.up.railway.app/health', {
  credentials: 'include'
}).then(r => r.json()).then(console.log)
// Should return {"status":"ok"} with no CORS error
```

---

## 10. Step 8 — Teardown AWS Resources

Only do this after the smoke test passes completely.

### 10.1 Delete App Runner services

```bash
aws apprunner list-services --region us-east-1

aws apprunner delete-service --service-arn <backend-arn> --region us-east-1
aws apprunner delete-service --service-arn <frontend-arn> --region us-east-1
```

### 10.2 Delete RDS instance

```bash
# Permanently deletes all data — ensure Neon restore was verified first
aws rds delete-db-instance \
  --db-instance-identifier idealens-postgres \
  --skip-final-snapshot \
  --delete-automated-backups \
  --region us-east-1
```

### 10.3 Delete VPC connector

```bash
aws apprunner delete-vpc-connector \
  --vpc-connector-arn <connector-arn> \
  --region us-east-1
```

### 10.4 Delete ECR repositories

```bash
aws ecr delete-repository --repository-name idealens-backend --force --region us-east-1
aws ecr delete-repository --repository-name idealens-frontend --force --region us-east-1
```

### 10.5 Delete Secrets Manager entries

```bash
aws secretsmanager delete-secret --secret-id idealens/DATABASE_URL --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id idealens/JWT_SECRET --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id idealens/API_KEY_ENCRYPTION_KEY --force-delete-without-recovery
```

### 10.6 Delete security group and RDS subnet group

```bash
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=idealens-rds-sg" \
  --query "SecurityGroups[0].GroupId" --output text)

aws ec2 delete-security-group --group-id $SG_ID
aws rds delete-db-subnet-group --db-subnet-group-name idealens-subnet-group
```

---

## 11. Environment Variable Reference

### Railway backend (set in Railway dashboard → Variables)

| Variable | Description | How to generate |
|----------|-------------|-----------------|
| `ENVIRONMENT` | `production` | — |
| `DATABASE_URL` | `postgresql+asyncpg://...neon.tech/neondb` | From Neon dashboard |
| `JWT_SECRET` | Min 32 chars | `openssl rand -hex 32` |
| `API_KEY_ENCRYPTION_KEY` | Fernet key | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `FRONTEND_URLS` | Comma-separated Vercel origins | e.g. `https://idealens.vercel.app` |

### Vercel frontend (set via `vercel env add` or dashboard)

| Variable | Value |
|----------|-------|
| `PUBLIC_API_URL` | `https://idealens-production.up.railway.app` |

---

## 12. Rollback Plan

The AWS stack is untouched until Step 8 — rolling back is just switching traffic back.

```
1. Both stacks run in parallel during testing — no cutover required
2. Old AWS stack continues serving at its App Runner URL until you delete it
3. Only decommission AWS (Step 8) after the full smoke test passes on the new stack
4. If JWT_SECRET and API_KEY_ENCRYPTION_KEY are kept the same, existing sessions and
   encrypted API keys are valid on both stacks simultaneously
```

> The only irreversible step is Step 8. Everything before that is additive.

---

## 13. Cost Reference

| Component | Cost |
|-----------|------|
| Railway (Hobby plan) | $5/month — includes $5 usage credit; a small persistent backend typically stays within this |
| Neon PostgreSQL | €0 (free tier: 0.5 GB storage, auto-suspend after 5 min idle) |
| Vercel frontend | €0 (free tier: 100 GB bandwidth, unlimited deployments) |
| **Total** | **~$5/month** |

> **Neon auto-suspend:** on the free tier, Neon suspends compute after 5 minutes of inactivity. The first query after suspension adds ~500ms latency. Only affects the very first request after an idle period.

---

## Appendix: Useful Commands

```bash
# View Railway logs
railway logs --service idealens-backend

# Open Railway shell (one-off commands)
railway shell --service idealens-backend

# Run Alembic migration via Railway
railway run --service idealens-backend -- uv run alembic upgrade head

# Redeploy without code changes
railway up --service idealens-backend --detach

# List Railway environment variables
railway variables --service idealens-backend

# Vercel — list deployments
vercel ls

# Vercel — view environment variables
vercel env ls

# Test SSE endpoint directly
curl -N \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","message":"test","graph_state":{"nodes":[],"edges":[]},"model":"claude-sonnet-4-6"}' \
  https://idealens-production.up.railway.app/api/chat
```