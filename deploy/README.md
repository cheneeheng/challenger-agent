# Deployment

Both services (backend and frontend) are containerised and deployed independently.

| Provider | Backend | Frontend | Registry |
|---|---|---|---|
| AWS | App Runner | App Runner | ECR |
| GCP | Cloud Run | Cloud Run | Artifact Registry |
| Azure | Container Apps | Container Apps | ACR |

---

## Docker assets

| File | Purpose |
|---|---|
| `Dockerfile.backend` | Production image — Python 3.12 + uv, deps cached in a separate layer |
| `Dockerfile.frontend` | Multi-stage build — Bun builder + Node 24 Alpine runner; accepts `PUBLIC_API_URL` build arg (compiled into bundle by Vite) |
| `docker-compose.dev.yml` | PostgreSQL only — used by `make db` for local dev |
| `docker-compose.yaml` | Full app (backend + frontend); reads env vars from `../.env` |

---

## Provider guides

- [AWS (App Runner + RDS)](aws/README.md) — includes RDS, VPC connector, Secrets Manager setup
- **GCP** — `gcp/deploy.sh` is an initial placeholder. Provisions Cloud Run + Artifact Registry. Database and secrets management not yet wired up.
- **Azure** — `azure/deploy.sh` is an initial placeholder. Provisions Container Apps + ACR. Database and secrets management not yet wired up.

---

## Quick start (any provider)

All scripts read from the root `.env` automatically. Fill in the relevant
section of `.env`, then run the script.

```bash
# AWS — see deploy/aws/README.md for full setup (RDS, VPC connector, etc.)
bash deploy/aws/deploy.sh

# GCP
bash deploy/gcp/deploy.sh

# Azure
bash deploy/azure/deploy.sh
```

Each script is idempotent — safe to re-run to deploy a new image version.

---

## Environment variables

See the [root README](../README.md#environment-variables) for the full variable
reference. In cloud deployments, pass secrets via the provider's native
secret/env mechanism — never bake them into images.

---

## CI/CD via GitHub Actions

Three manually-triggered workflows live in `.github/workflows/`:

| Workflow | Trigger |
|---|---|
| `deploy-gcp.yaml` | `workflow_dispatch` |
| `deploy-aws.yaml` | `workflow_dispatch` |
| `deploy-azure.yaml` | `workflow_dispatch` |

To trigger automatically on push to `main`, change `on: workflow_dispatch` to:

```yaml
on:
  push:
    branches: [main]
```

### Required secrets per provider

**GCP** — set in repo Settings → Secrets:
- `GCP_PROJECT`, `GCP_REGION`, `APP_NAME`
- `GCP_SA_KEY` — service account JSON with Artifact Registry Writer + Cloud Run Admin + Service Account User

**AWS** — set in repo Settings → Secrets:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `APP_NAME`
- `APPRUNNER_ECR_ROLE_ARN` — IAM role with `AWSAppRunnerServicePolicyForECRAccess`
- `DATABASE_URL`, `JWT_SECRET`, `API_KEY_ENCRYPTION_KEY`
- `VPC_CONNECTOR_ARN` — required when RDS is in a private VPC (output of `setup-infra.sh`)
- See [deploy/aws/README.md](aws/README.md) for the full setup procedure.

**Azure** — set in repo Settings → Secrets:
- `AZURE_CREDENTIALS` (service principal JSON), `RESOURCE_GROUP`, `APP_NAME`, `LOCATION`

---

## Terraform

The deploy scripts use each provider's CLI directly. They are idempotent and readable without any additional tooling. The AWS script now also handles VPC networking for a private RDS instance.

Migrate to Terraform when any of the following become true:

- **You add a database** — provisioning RDS, Cloud SQL, or Azure PostgreSQL alongside the app means multiple resources with interdependencies that Terraform handles better than shell scripts.
- **You need private networking** — VPCs, subnets, security groups, and private service connections are painful to manage imperatively.
- **You have multiple environments** — Terraform variable files make dev/staging/prod trivial; shell scripts require duplicating or parameterising everything manually.
- **You need drift detection** — `terraform plan` shows when actual infrastructure has diverged from the declared state. CLI scripts have no equivalent.
- **Team ownership** — Terraform state gives the whole team a shared, auditable record of what is deployed and who changed it.

At that point, replace the scripts with a `deploy/terraform/` directory containing one module per provider, and store state remotely (S3 + DynamoDB for AWS, GCS for GCP, Azure Blob Storage for Azure).

---

## Adding a database

**AWS** — handled by `deploy/aws/setup-infra.sh`. See [deploy/aws/README.md](aws/README.md).

**GCP / Azure** — provision a managed database (Cloud SQL or Azure Database for
PostgreSQL), inject `DATABASE_URL` as an environment variable, and run Alembic
migrations before the new image goes live:

```bash
DATABASE_URL='postgresql+asyncpg://...' \
  cd backend && uv run alembic upgrade head
```
