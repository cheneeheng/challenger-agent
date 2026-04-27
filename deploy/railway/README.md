# Deploy — Railway + Neon + Vercel

Near-free alternative to the AWS stack (~$5/month vs ~$26/month).

| Component | Provider | Cost |
|-----------|----------|------|
| Backend (persistent container) | Railway Hobby | $5/month |
| PostgreSQL | Neon | Free (0.5 GB) |
| Frontend (global CDN) | Vercel | Free |

Full step-by-step instructions: [`docs/plan/05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT.md`](../../docs/plan/05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT.md)

---

## Quick-start

### Prerequisites

```bash
npm install -g @railway/cli vercel
railway login
vercel login
```

You also need accounts at [neon.tech](https://neon.tech), [railway.app](https://railway.app) (Hobby plan), and [vercel.com](https://vercel.com).

---

### Step 1 — Neon (database)

1. Create a project at [console.neon.tech](https://console.neon.tech) — region closest to your Railway deployment.
2. Copy the **pooled** connection string from Connection Details.
3. Convert prefix: `postgresql://` → `postgresql+asyncpg://`, drop `?sslmode=require`.
4. Run migrations:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://<user>:<pw>@<host>/neondb" \
  uv run alembic upgrade head
```

The backend engine automatically enables SSL when the URL contains `neon.tech` (`backend/app/db/base.py`).

---

### Step 2 — Railway (backend)

```bash
cd backend
railway init          # name the project "idealens"
railway up            # builds from deploy/Dockerfile.backend, deploys as persistent container
```

Set these variables in the Railway dashboard → Variables:

| Variable | Value |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...neon.tech/neondb` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `API_KEY_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `FRONTEND_URLS_RAW` | *(set after Vercel deploy)* |

Verify:

```bash
curl https://<your-app>.up.railway.app/health
# → {"status":"ok","environment":"production"}
```

---

### Step 3 — Vercel (frontend)

```bash
cd frontend
bun install                  # installs @sveltejs/adapter-vercel
ADAPTER=vercel bun run build  # smoke-test the Vercel build locally (optional)
vercel --prod
vercel env add PUBLIC_API_URL production
# enter: https://<your-app>.up.railway.app
```

Note your Vercel URL (e.g. `https://idealens.vercel.app`).

---

### Step 4 — CORS + cookie

Set `FRONTEND_URLS_RAW` in Railway Variables to your Vercel URL:

```
FRONTEND_URLS_RAW = https://idealens.vercel.app
```

The cookie `SameSite` attribute is already set to `lax` in `backend/app/api/routes/auth.py`, which allows the httpOnly refresh token cookie to work across origins.

---

### Step 5 — CI/CD

Add these secrets to GitHub → Settings → Secrets and variables → Actions:

| Secret | How to get |
|--------|-----------|
| `RAILWAY_TOKEN` | Railway → Account → Tokens → New Token |
| `VERCEL_TOKEN` | Vercel → Account → Tokens |
| `VERCEL_ORG_ID` | `vercel whoami` or Vercel Settings |
| `VERCEL_PROJECT_ID_SVELTE` | `frontend/.vercel/project.json` after first deploy |

The workflow at `.github/workflows/deploy.yml` auto-deploys on every push to `main`.

---

## Environment variable reference

### Railway (backend)

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...neon.tech/neondb` |
| `JWT_SECRET` | Min 32 chars, hex |
| `API_KEY_ENCRYPTION_KEY` | Fernet key |
| `FRONTEND_URLS_RAW` | Comma-separated Vercel origins |

### Vercel (frontend)

| Variable | Value |
|----------|-------|
| `PUBLIC_API_URL` | `https://<your-app>.up.railway.app` |
| `ADAPTER` | `vercel` |

---

## Useful commands

```bash
# View Railway logs
railway logs --service idealens-backend

# Run Alembic migration via Railway shell
railway run --service idealens-backend -- uv run alembic upgrade head

# Redeploy without code changes
railway up --service idealens-backend --detach

# List Vercel deployments
vercel ls

# Test SSE endpoint
curl -N \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","message":"test","graph_state":{"nodes":[],"edges":[]},"model":"claude-sonnet-4-6"}' \
  https://<your-app>.up.railway.app/api/chat
```
