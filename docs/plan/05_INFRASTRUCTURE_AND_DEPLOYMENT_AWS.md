---
doc: 05_INFRASTRUCTURE_AND_DEPLOYMENT_AWS
status: amended
version: 2
created: 2026-04-18
amended: 2026-04-18
scope: AWS deployment — EC2 t4g.small (API) + S3/CloudFront (frontend) + RDS; optimised for early-stage, ~$26/month
amendments:
  - v2 (2026-04-18): Replaced ECS Fargate + ALB with EC2 t4g.small + Nginx + S3/CloudFront. Eliminates $20/month ALB and $7/month Fargate web task. Saves ~$30/month. Suitable for early-stage; upgrade path to ECS documented in §16.
relates_to:
  - 01_PROJECT_PLAN
  - 02_TODOS
  - 03_ARCHITECTURE
  - 05_INFRASTRUCTURE_AND_DEPLOYMENT_ALT
---

# INFRASTRUCTURE & DEPLOYMENT — AWS (EC2 + S3/CloudFront)

**Stack:** Python 3.12 · FastAPI · Docker · Nginx · Terraform · AWS EC2 t4g.small · S3 · CloudFront · ACM · RDS PostgreSQL · ECR · Secrets Manager · GitHub Actions

> Early-stage deployment optimised for cost without sacrificing reliability or the ability to scale.
> Frontend (SvelteKit SPA) served from S3 + CloudFront — ~$0.10/month at low traffic.
> API runs on a single EC2 t4g.small (ARM/Graviton2) behind Nginx — ~$12/month.
> No ALB. TLS: ACM on CloudFront (frontend) + Let's Encrypt on EC2 Nginx (API).
> Upgrade path to ECS Fargate + ALB documented in §16 — zero application code changes required.

---

## 1. Philosophy

This setup is deliberately right-sized for an early-stage app. IdeaLens has two runtime components:

1. **A static SPA** — SvelteKit with `ssr = false` produces a purely static build. It does not need a running server. S3 + CloudFront is the natural and cheapest fit.
2. **A FastAPI API** — handles auth, SSE streaming, and DB access. It needs a persistent process. A single EC2 instance running Docker + Nginx covers this cleanly.

The frontend and API are **decoupled at deployment time**. The frontend makes cross-origin API calls to the EC2 instance's domain. There is no need for a load balancer to route between them — CloudFront handles the frontend entirely, and EC2 Nginx handles the API directly.

**SSE compatibility:** The app streams LLM tokens via SSE with a 15-second heartbeat ping. EC2 + Nginx handles persistent connections correctly with `proxy_read_timeout 120s` and `proxy_buffering off`. There is no ALB idle timeout to work around — this is actually a simpler and more reliable setup for SSE than Fargate + ALB, where the ALB's idle timeout had to be manually tuned.

**Reliability trade-off vs Fargate:** ECS Fargate auto-restarts failed tasks. On EC2, `restart: always` in Docker Compose handles this — a crashed container restarts in ~5 seconds. For an early-stage app this is equivalent in practice.

All AWS resources are managed exclusively through Terraform. No manual Console changes after bootstrap.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     PUBLIC INTERNET                     │
└──────────────┬──────────────────────────┬───────────────┘
               │ HTTPS (*.idealens.dev)   │ HTTPS (api.idealens.dev)
    ┌──────────▼──────────┐   ┌───────────▼───────────────┐
    │   CloudFront CDN    │   │   EC2 t4g.small           │
    │   ACM cert (free)   │   │   Nginx + Let's Encrypt   │
    │   Origin: S3 bucket │   │   → Docker: FastAPI 8000  │
    └──────────┬──────────┘   └───────────┬───────────────┘
               │                          │ TCP 5432
    ┌──────────▼──────────┐   ┌───────────▼───────────┐
    │   S3 Bucket         │   │   RDS db.t4g.micro    │
    │   (static SPA)      │   │   PostgreSQL 16       │
    │   private + OAC     │   │   private subnet      │
    └─────────────────────┘   └───────────────────────┘
```

**Domain setup:**
- `idealens.dev` → CloudFront (frontend SPA)
- `api.idealens.dev` → EC2 Elastic IP (API)

The frontend's `PUBLIC_API_URL` is set to `https://api.idealens.dev` at build time (baked into the static bundle). CORS on the API allows `https://idealens.dev`.

---

## 3. Terraform Module Structure

```
infra/
├── backend.tf              # S3 remote state + DynamoDB lock
├── main.tf                 # wires modules together
├── variables.tf
├── terraform.tfvars        # non-secret values (committed)
├── terraform.tfvars.example
├── outputs.tf              # EC2 public IP, CloudFront domain, RDS endpoint
└── modules/
    ├── networking/         # VPC, public subnet, security groups
    ├── ecr/                # idealens-api only (no web container image needed)
    ├── ec2/                # t4g.small, Elastic IP, instance role, key pair, user data
    ├── rds/                # PostgreSQL 16 + subnet group (private — only ec2 can reach it)
    ├── s3/                 # static site bucket + OAC policy
    ├── cloudfront/         # distribution, OAC, ACM cert (must be us-east-1), HTTPS redirect
    └── secrets/            # Secrets Manager entries (values set manually post-apply)
```

---

## 4. `terraform.tfvars`

```hcl
aws_region = "us-east-1"

# EC2 — ARM/Graviton2, right-sized for early-stage
ec2_instance_type = "t4g.small"    # 2 vCPU, 2 GB RAM
ec2_key_pair_name = "idealens-key" # created in bootstrap step (§6)

# RDS — Graviton2 burstable, sufficient for early-stage traffic
rds_instance_class    = "db.t4g.micro"  # 2 vCPU, 1 GB RAM
rds_allocated_storage = 20              # GB, gp2
rds_engine_version    = "16"

# Domains (leave empty to use AWS default hostnames until domain is acquired)
frontend_domain = "idealens.dev"
api_domain      = "api.idealens.dev"
```

---

## 5. Security Groups

```
sg-ec2 (API instance):
  inbound:  TCP 443  from 0.0.0.0/0    (HTTPS — Nginx terminates TLS)
            TCP 80   from 0.0.0.0/0    (HTTP → HTTPS redirect by Nginx)
            TCP 22   from <your-ip>/32  (SSH — restrict to your IP only)
  outbound: all                          (Anthropic API, ECR pull, Secrets Manager, RDS)

sg-rds:
  inbound:  TCP 5432 from sg-ec2 ONLY
  outbound: none
```

No ALB security group needed. The S3 bucket is private; only CloudFront's OAC can read it. CloudFront itself is a managed service with no security group.

---

## 6. Bootstrap Procedure (one-time)

```bash
# 1. Create S3 bucket for Terraform state
aws s3 mb s3://idealens-tf-state --region us-east-1
aws s3api put-bucket-versioning \
  --bucket idealens-tf-state \
  --versioning-configuration Status=Enabled

# 2. Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name idealens-tf-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# 3. Create EC2 key pair (for SSH access)
aws ec2 create-key-pair \
  --key-name idealens-key \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/idealens-key.pem
chmod 400 ~/.ssh/idealens-key.pem

# 4. Generate and store secrets
python -c "import secrets; print(secrets.token_hex(64))"
aws secretsmanager create-secret --name idealens/JWT_SECRET --secret-string "<value>"

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
aws secretsmanager create-secret --name idealens/API_KEY_ENCRYPTION_KEY --secret-string "<value>"

# 5. Initialize and apply Terraform
cd infra
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars

# 6. Store DATABASE_URL (RDS endpoint now known from Terraform output)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
aws secretsmanager create-secret \
  --name idealens/DATABASE_URL \
  --secret-string "postgresql+asyncpg://idealens:<password>@${RDS_ENDPOINT}/idealens"

# 7. Note outputs for DNS and CI setup
terraform output ec2_public_ip      # → point api.idealens.dev A record here
terraform output cloudfront_domain  # → point idealens.dev CNAME here (or use as-is without custom domain)
terraform output ec2_instance_id    # → set as EC2_INSTANCE_ID GitHub secret
```

---

## 7. EC2 Instance Setup

The `ec2` Terraform module provisions a `t4g.small` Amazon Linux 2023 instance with an instance role (§11) and the following user data on first boot:

```bash
#!/bin/bash
dnf update -y
dnf install -y docker nginx certbot python3-certbot-nginx awscli
systemctl enable docker nginx
systemctl start docker

# Docker Compose plugin (ARM64 build)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/idealens
```

After `terraform apply`, SSH in once to finish setup:

```bash
ssh -i ~/.ssh/idealens-key.pem ec2-user@<ec2-public-ip>

# Obtain TLS cert for the API domain (free, auto-renewing)
certbot --nginx -d api.idealens.dev --non-interactive --agree-tos -m your@email.com

# Write .env by pulling from Secrets Manager
aws secretsmanager get-secret-value --secret-id idealens/DATABASE_URL --query SecretString --output text
aws secretsmanager get-secret-value --secret-id idealens/JWT_SECRET --query SecretString --output text
aws secretsmanager get-secret-value --secret-id idealens/API_KEY_ENCRYPTION_KEY --query SecretString --output text
# Write these values to /opt/idealens/.env

# Pull and start the API container
cd /opt/idealens
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ecr-registry>
docker compose -f docker-compose.prod.yml up -d

# Run initial DB migration
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

---

## 8. Nginx Configuration

`/etc/nginx/conf.d/idealens-api.conf`:

```nginx
server {
    listen 80;
    server_name api.idealens.dev;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.idealens.dev;

    ssl_certificate     /etc/letsencrypt/live/api.idealens.dev/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.idealens.dev/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # SSE endpoint — disable buffering so tokens stream immediately to the browser
    location /api/chat {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';      # required for SSE keep-alive
        proxy_buffering off;                 # stream tokens as they arrive
        proxy_cache off;
        proxy_read_timeout 120s;             # heartbeat fires every 15s; 120s gives ample margin
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }

    # All other routes (REST API + auth)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

**Why 120s read timeout works with SSE:** Nginx resets its `proxy_read_timeout` countdown on every byte received from upstream. The API emits a `ping` event every 15 seconds during streaming. The timeout only triggers if no bytes arrive for 120 consecutive seconds — which can only happen if the API process hangs entirely, which is the correct scenario to time out on.

---

## 9. S3 + CloudFront (Frontend)

SvelteKit's `npm run build` with `ssr = false` produces a static `build/` directory. This uploads to S3 and is served via CloudFront.

**S3 bucket:** private, versioning enabled. OAC policy allows CloudFront to read; no public access.

**CloudFront distribution:**
- Origin: S3 bucket via OAC
- HTTPS only (HTTP → HTTPS 301 redirect)
- ACM certificate attached — must be provisioned in `us-east-1` regardless of the app's region
- Custom error responses: `403 → /index.html (200)` and `404 → /index.html (200)` — required for SPA client-side routing so refreshing `/session/abc` doesn't return a 403 from S3
- Cache policy: `index.html` gets `Cache-Control: no-cache` so new deploys propagate immediately; Vite asset filenames are content-hashed so they get long TTLs (~1 year)

---

## 10. Production Docker Compose (EC2)

`/opt/idealens/docker-compose.prod.yml`:

```yaml
version: "3.9"
services:
  api:
    image: <ecr-registry>/idealens-api:latest
    restart: always            # auto-restart on crash — equivalent to ECS task restart policy
    ports:
      - "127.0.0.1:8000:8000" # loopback only — Nginx proxies; port never exposed to internet
    env_file: .env
    environment:
      ENVIRONMENT: production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

`restart: always` means Docker automatically restarts the container on crash, OOM kill, or unhandled exception — without any ECS orchestration layer.

---

## 11. IAM

### EC2 Instance Role
Attached to the instance profile. Allows ECR pulls and secret reads without any credentials on disk.

```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",
    "ecr:BatchGetImage",
    "ecr:GetDownloadUrlForLayer",
    "secretsmanager:GetSecretValue"
  ],
  "Resource": [
    "arn:aws:ecr:us-east-1:*:repository/idealens-api",
    "arn:aws:secretsmanager:us-east-1:*:secret:idealens/*"
  ]
}
```

Also attach `AmazonSSMManagedInstanceCore` so GitHub Actions can run commands on the instance via SSM without storing SSH keys in CI.

### GitHub Actions IAM User (`idealens-deploy`)

```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:PutImage",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload",
    "s3:PutObject",
    "s3:DeleteObject",
    "s3:ListBucket",
    "cloudfront:CreateInvalidation",
    "ssm:SendCommand",
    "ssm:GetCommandInvocation"
  ],
  "Resource": "*"
}
```

---

## 12. Migration Strategy

### First deployment
SSH into EC2 and run manually after the container is up:

```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

### Subsequent deployments
Migrations run via SSM in CI before the new container starts:

```bash
aws ssm send-command \
  --instance-ids $EC2_INSTANCE_ID \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "cd /opt/idealens",
    "aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ecr>",
    "docker compose -f docker-compose.prod.yml pull",
    "docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head",
    "docker compose -f docker-compose.prod.yml up -d"
  ]'
```

Every Alembic migration must have a working `downgrade()` function.

---

## 13. API Dockerfile

`apps/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
RUN pip install uv

FROM base AS development
COPY pyproject.toml uv.lock .
RUN uv sync
COPY . .
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
COPY pyproject.toml uv.lock .
RUN uv sync --no-dev
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Built with `--platform linux/arm64` in CI to target the Graviton2 EC2 instance.

---

## 14. CI/CD Pipeline

### `.github/workflows/ci.yml` (on PR to main)

```yaml
jobs:
  backend:
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_USER: idealens, POSTGRES_PASSWORD: idealens, POSTGRES_DB: idealens_test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install uv && cd apps/api && uv sync
      - run: cd apps/api && ruff check .
      - run: cd apps/api && pytest
        env: { TEST_DATABASE_URL: "postgresql+asyncpg://idealens:idealens@localhost:5432/idealens_test" }

  frontend-svelte:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd apps/web-svelte && npm ci
      - run: cd apps/web-svelte && npx svelte-check
      - run: cd apps/web-svelte && npx vitest run
```

### `.github/workflows/deploy.yml` (on push to main)

```yaml
jobs:
  deploy-api:
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}, ... }
      - uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push API image (ARM64)
        run: |
          docker buildx build \
            --platform linux/arm64 \
            --target production \
            -t ${{ secrets.ECR_REGISTRY }}/idealens-api:$GITHUB_SHA \
            -t ${{ secrets.ECR_REGISTRY }}/idealens-api:latest \
            --push apps/api

      - name: Migrate and restart via SSM
        run: |
          CMD_ID=$(aws ssm send-command \
            --instance-ids ${{ secrets.EC2_INSTANCE_ID }} \
            --document-name "AWS-RunShellScript" \
            --parameters 'commands=[
              "cd /opt/idealens",
              "aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}",
              "docker compose -f docker-compose.prod.yml pull",
              "docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head",
              "docker compose -f docker-compose.prod.yml up -d"
            ]' \
            --query Command.CommandId --output text)
          aws ssm wait command-executed \
            --command-id $CMD_ID \
            --instance-id ${{ secrets.EC2_INSTANCE_ID }}

  deploy-frontend:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - uses: aws-actions/configure-aws-credentials@v4
        with: { aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}, ... }

      - name: Build SvelteKit SPA
        run: |
          cd apps/web-svelte && npm ci
          PUBLIC_API_URL=${{ secrets.API_URL }} npm run build

      - name: Upload to S3 and invalidate CloudFront
        run: |
          aws s3 sync apps/web-svelte/build/ s3://${{ secrets.S3_BUCKET }}/ --delete
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CF_DISTRIBUTION_ID }} \
            --paths "/*"
```

### GitHub Secrets required
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION              # us-east-1
ECR_REGISTRY            # <account_id>.dkr.ecr.us-east-1.amazonaws.com
EC2_INSTANCE_ID         # i-xxxxxxxxxxxxxxxxx
S3_BUCKET               # idealens-frontend
CF_DISTRIBUTION_ID      # CloudFront distribution ID
API_URL                 # https://api.idealens.dev
```

---

## 15. Local Development

```bash
# Prerequisites: Docker Desktop, uv, Node 20+

# 1. Clone and setup
git clone <repo> && cd idealens
cp apps/api/.env.example apps/api/.env   # fill in JWT_SECRET and API_KEY_ENCRYPTION_KEY

# 2. Start API + Postgres
docker-compose up postgres api

# 3. Start frontend dev server (separate terminal)
cd apps/web-svelte && npm install && npm run dev   # http://localhost:3001

# 4. Run migrations (first time)
docker-compose exec api alembic upgrade head

# 5. Seed test data (optional)
docker-compose exec api python -m app.db.seed

# Access:
# SvelteKit frontend:  http://localhost:3001
# API docs:            http://localhost:8000/docs
```

---

## 16. Cost Summary

All figures are us-east-1 on-demand rates.

| Resource | Spec | Monthly (approx.) |
|---|---|---|
| EC2 t4g.small (ARM/Graviton2) | 2 vCPU, 2 GB RAM, 730h | ~$12 |
| RDS db.t4g.micro (ARM/Graviton2) | PostgreSQL 16, 20 GB gp2, single-AZ | ~$12 |
| S3 (frontend static files) | ~50 MB storage, minimal requests | ~$0.01 |
| CloudFront | ~1 GB/month transfer at low traffic | ~$0.09 |
| ECR (1 repo — API only) | ~500 MB image | ~$0.05 |
| Secrets Manager (3 secrets) | $0.40/secret/month | ~$1.20 |
| Let's Encrypt TLS (API) | Free, auto-renewing | $0 |
| ACM TLS (CloudFront) | Free | $0 |
| **Total** | | **~$26/month** |

**Compared to ECS Fargate + ALB (~$56/month), this saves ~$30/month (~54%)** by eliminating the ALB ($20/month) and Fargate web task ($7/month), and consolidating API compute onto a single EC2 instance instead of two separate Fargate tasks.

Anthropic API costs are fully user-paid — users supply their own API keys.

**When to migrate to ECS Fargate + ALB:** when you need horizontal scaling (multiple API instances), zero-downtime rolling deploys without SSM, or multi-AZ high availability. Zero application code changes required for that migration — only Terraform and Docker Compose configuration changes.

---

## 17. GCP (v2 — Placeholder)

When GCP support is added:
- Second Terraform workspace in `infra/gcp/`
- Cloud Run replaces EC2 (serverless containers, no instance to manage)
- Cloud Storage + Cloud CDN replaces S3 + CloudFront
- Cloud SQL replaces RDS
- Secret Manager replaces Secrets Manager
- Zero application code changes required