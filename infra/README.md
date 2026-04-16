# Infra

Docker assets for building and running the application.

| File | Purpose |
|---|---|
| `Dockerfile.backend` | Production image — Python 3.12 + uv, deps cached in a separate layer |
| `Dockerfile.frontend` | Multi-stage build — Bun builder + Node 24 Alpine runner |
| `docker-compose.dev.yml` | PostgreSQL only — used by `make db` for local dev |
| `docker-compose.yaml` | Full app (backend + frontend); reads env vars from `../.env` |

For cloud deployment scripts and CI/CD workflows see [`../deploy/`](../deploy/README.md).
