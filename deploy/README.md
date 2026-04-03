# Deployment

Both services (backend and frontend) are containerised and deployed independently.

| Provider | Backend | Frontend | Registry |
|---|---|---|---|
| AWS | App Runner | App Runner | ECR |
| GCP | Cloud Run | Cloud Run | Artifact Registry |
| Azure | Container Apps | Container Apps | ACR |

---

## Quick start (any provider)

```bash
# From repo root
export APP_NAME=myapp          # used for service and registry names

# AWS
export AWS_REGION=us-east-1
export APPRUNNER_ECR_ROLE_ARN=arn:aws:iam::123456789012:role/AppRunnerECRRole
bash deploy/aws/deploy.sh

# GCP
export GCP_PROJECT=my-gcp-project
export GCP_REGION=us-central1
bash deploy/gcp/deploy.sh

# Azure
export RESOURCE_GROUP=myapp-rg
export LOCATION=eastus
bash deploy/azure/deploy.sh
```

Each script is idempotent — safe to re-run to deploy a new image version.

---

## Environment variables

Both services read from `.env`. In cloud deployments, pass secrets via the
provider's native secret/env mechanism — never bake them into images.

Key vars to set in production:

| Variable | Service | Notes |
|---|---|---|
| `APP_ENV` | backend | Set to `production` |
| `SECRET_KEY` | backend | Generate: `openssl rand -hex 32` |
| `CORS_ORIGINS` | backend | Comma-separated frontend URL(s) |
| `DATABASE_URL` | backend | Add when using a database |
| `ORIGIN` | frontend | Required by adapter-node — must match public URL |
| `PUBLIC_API_BASE_URL` | frontend | Full URL of the backend service |

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
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_ACCOUNT_ID`, `APP_NAME`
- `APPRUNNER_ECR_ROLE_ARN` — IAM role with `AmazonEC2ContainerRegistryReadOnly`

**Azure** — set in repo Settings → Secrets:
- `AZURE_CREDENTIALS` (service principal JSON), `RESOURCE_GROUP`, `APP_NAME`, `LOCATION`

---

## Terraform

The deploy scripts use each provider's CLI directly, which is the right fit for this template's scope — two stateless containers with no networking complexity. The scripts are idempotent and readable without any additional tooling.

Migrate to Terraform when any of the following become true:

- **You add a database** — provisioning RDS, Cloud SQL, or Azure PostgreSQL alongside the app means multiple resources with interdependencies that Terraform handles better than shell scripts.
- **You need private networking** — VPCs, subnets, security groups, and private service connections are painful to manage imperatively.
- **You have multiple environments** — Terraform variable files make dev/staging/prod trivial; shell scripts require duplicating or parameterising everything manually.
- **You need drift detection** — `terraform plan` shows when actual infrastructure has diverged from the declared state. CLI scripts have no equivalent.
- **Team ownership** — Terraform state gives the whole team a shared, auditable record of what is deployed and who changed it.

At that point, replace the scripts with a `deploy/terraform/` directory containing one module per provider, and store state remotely (S3 + DynamoDB for AWS, GCS for GCP, Azure Blob Storage for Azure).

---

## Adding a database

For managed databases, provision them outside this template and inject the
`DATABASE_URL` as an environment variable. Recommended services:

| Provider | Service |
|---|---|
| AWS | RDS (Postgres) or Aurora Serverless |
| GCP | Cloud SQL (Postgres) |
| Azure | Azure Database for PostgreSQL |

Use Alembic for migrations. Run migrations as a pre-deploy step or a one-off
container task before the new image goes live.
