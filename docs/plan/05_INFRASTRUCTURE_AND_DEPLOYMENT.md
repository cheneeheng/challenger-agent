# INFRASTRUCTURE & DEPLOYMENT
> Authoritative guide for Terraform, AWS, CI/CD, Docker, and local development setup.
> Two frontends exist in the repo; only one is deployed to production at a time.
> The active frontend is selected via the DEPLOY_FRONTEND secret (react|svelte).

---

## 1. Philosophy

All AWS resources are managed exclusively through Terraform. No manual AWS Console changes after bootstrap. Every resource is reproducible and version-controlled. GCP is added in v2 as a second Terraform workspace — zero application code changes required.

Both frontend images are built and pushed to ECR on every deploy. Only the selected frontend's image is used to update the web ECS service. Switching frontends is a deploy-time decision — change `DEPLOY_FRONTEND` and re-run the workflow. No Terraform changes, no infra rebuild.

---

## 2. Terraform Module Structure

```
infra/
├── backend.tf              # S3 remote state + DynamoDB lock
├── main.tf                 # wires modules together
├── variables.tf            # input variable declarations
├── terraform.tfvars        # non-secret values (committed)
├── terraform.tfvars.example
├── outputs.tf              # ALB DNS, ECR URLs, RDS endpoint
└── modules/
    ├── networking/         # security groups on default VPC
    ├── ecr/                # idealens-api + idealens-web-react + idealens-web-svelte
    ├── rds/                # PostgreSQL 16 instance + subnet group
    ├── secrets/            # Secrets Manager entries (values set manually)
    ├── iam/                # ECS task execution role + task role
    ├── alb/                # ALB, HTTP->HTTPS redirect, HTTPS listener, target groups, rules
    ├── acm/                # TLS certificate (DNS validation)
    └── ecs/                # cluster, 2 services (api + web), migrate task definition
                            # web task definition image URI is set at deploy time
```

---

## 3. `terraform.tfvars`

```hcl
aws_region = "us-east-1"

# ECS task sizes
api_task_cpu    = 512     # 0.5 vCPU
api_task_memory = 1024    # 1 GB
web_task_cpu    = 256     # 0.25 vCPU — same var regardless of which frontend is deployed
web_task_memory = 512     # 512 MB
ecs_desired_count = 1

# RDS
rds_instance_class    = "db.t3.micro"
rds_allocated_storage = 20
rds_engine_version    = "16"

# ALB — must be >= SSE heartbeat interval (15s) + comfortable buffer
alb_idle_timeout = 60

# Domain (update when domain is acquired)
domain_name = ""
```

---

## 4. Security Groups

```
sg-alb:
  inbound:  TCP 443 from 0.0.0.0/0
            TCP 80  from 0.0.0.0/0  (redirected to 443)
  outbound: all to sg-web, sg-api

sg-web (active frontend ECS tasks):
  inbound:  TCP 80 from sg-alb
  outbound: all  (ECR pull, Secrets Manager)

sg-api (uvicorn ECS tasks):
  inbound:  TCP 8000 from sg-alb
  outbound: all  (Anthropic API, ECR, Secrets Manager)
            TCP 5432 to sg-rds

sg-rds:
  inbound:  TCP 5432 from sg-api ONLY
  outbound: none
```

A single `sg-web` covers whichever frontend is deployed. Both frontend containers expose
port 80 in production — React via nginx, SvelteKit via its Node server with `PORT=80`.
No security group changes are required when switching frontends. ECS tasks have public IPs
(required to reach ECR and Anthropic without NAT gateway). RDS is unreachable from the
internet; only api tasks reach it via sg-rds.

---

## 5. ALB Routing Rules (priority order)

```
Listener: HTTPS (443), ACM certificate attached

Priority 1: path /api/chat*  -> api target group  (SSE — listed separately for read timeout)
Priority 2: path /api/*      -> api target group
Priority 3: path /auth/*     -> api target group
Priority 4: path /*          -> web target group   (catch-all — whichever frontend is deployed)

HTTP listener (80): redirect all -> HTTPS 301
```

The `web` target group points to the currently deployed frontend container on port 80.
No ALB rule changes are required when switching frontends — only the ECS service's task
definition (and therefore the running container image) changes.

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

# 3. Generate and store secrets in AWS Secrets Manager
python -c "import secrets; print(secrets.token_hex(64))"
aws secretsmanager create-secret --name idealens/JWT_SECRET --secret-string "<output>"

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
aws secretsmanager create-secret --name idealens/API_KEY_ENCRYPTION_KEY --secret-string "<output>"

# 4. Initialize and apply Terraform
cd infra
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars

# 5. Store DATABASE_URL now that RDS endpoint is known (from terraform output)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
aws secretsmanager create-secret \
  --name idealens/DATABASE_URL \
  --secret-string "postgresql+asyncpg://idealens:<password>@${RDS_ENDPOINT}/idealens"

# 6. Run initial database migration
# See §8 — Migration Strategy
```

---

## 7. IAM Roles

### ECS Task Execution Role
Allows ECS to pull images from ECR and inject secrets from Secrets Manager.
The same role is used by both the api and web services.
- Managed policy: `AmazonECSTaskExecutionRolePolicy`
- Inline policy:
  ```json
  {
    "Effect": "Allow",
    "Action": ["secretsmanager:GetSecretValue"],
    "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:idealens/*"
  }
  ```

### ECS Task Role (api service)
In v1: no additional permissions (secrets injected as env vars; no direct AWS SDK calls from app code).

### GitHub Actions IAM User (`idealens-deploy`)
Scoped to only what CI/CD needs (covers all three ECR repos and both ECS services):
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
    "ecs:UpdateService",
    "ecs:DescribeServices",
    "ecs:RegisterTaskDefinition",
    "ecs:RunTask",
    "ecs:DescribeTasks"
  ],
  "Resource": "*"
}
```

Terraform is run locally — not in CI — to avoid storing broad provisioning permissions in GitHub Secrets.

---

## 8. Migration Strategy

### First deployment
A separate `idealens-api-migrate` ECS task definition is provisioned by Terraform. It uses
the same image and env vars as the api service but overrides the command to `alembic upgrade head`.

```bash
TASK_DEF_ARN=$(terraform output -raw migrate_task_definition_arn)
SUBNET_ID=$(terraform output -raw public_subnet_id)
SG_API=$(terraform output -raw sg_api_id)

aws ecs run-task \
  --cluster idealens \
  --task-definition $TASK_DEF_ARN \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$SG_API],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

### Subsequent deployments
Migrations run automatically in `deploy.yml` before updating ECS services:
```
1. Build + push api image and selected frontend image
2. aws ecs run-task (migration) -> wait for completion
3. aws ecs update-service (api) -> rolling deploy
4. aws ecs update-service (web) -> rolling deploy with selected frontend image
5. aws ecs wait services-stable --services idealens-api idealens-web
```

Every Alembic migration must have a working `downgrade()` function.

---

## 9. CI/CD Pipeline

### `.github/workflows/ci.yml` (on PR to main)

Three parallel jobs — backend runs once; each frontend runs independently.
CI always tests both frontends regardless of which one is set to deploy.

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
      - run: cd apps/api && mypy app/
      - run: cd apps/api && pytest
        env: { TEST_DATABASE_URL: "postgresql+asyncpg://idealens:idealens@localhost:5432/idealens_test" }

  frontend-react:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd apps/web-react && npm ci
      - run: cd apps/web-react && npx eslint src/
      - run: cd apps/web-react && npx tsc --noEmit
      - run: cd apps/web-react && npx vitest run

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

Both frontend images are always built and pushed to ECR. Only the selected frontend's
image is used to update the web ECS service. This means switching frontends in the future
requires only changing the `DEPLOY_FRONTEND` secret — no rebuild needed.

```yaml
jobs:
  deploy:
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}, ... }
      - uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push api image
        run: |
          docker build --target production -t $ECR_REGISTRY/idealens-api:$GITHUB_SHA apps/api
          docker tag $ECR_REGISTRY/idealens-api:$GITHUB_SHA $ECR_REGISTRY/idealens-api:latest
          docker push $ECR_REGISTRY/idealens-api:$GITHUB_SHA
          docker push $ECR_REGISTRY/idealens-api:latest

      - name: Build and push web-react image
        run: |
          docker build --target production \
            -t $ECR_REGISTRY/idealens-web-react:$GITHUB_SHA apps/web-react
          docker tag $ECR_REGISTRY/idealens-web-react:$GITHUB_SHA $ECR_REGISTRY/idealens-web-react:latest
          docker push $ECR_REGISTRY/idealens-web-react:$GITHUB_SHA
          docker push $ECR_REGISTRY/idealens-web-react:latest

      - name: Build and push web-svelte image
        run: |
          docker build --target production \
            --build-arg PUBLIC_API_URL="" \
            -t $ECR_REGISTRY/idealens-web-svelte:$GITHUB_SHA apps/web-svelte
          docker tag $ECR_REGISTRY/idealens-web-svelte:$GITHUB_SHA $ECR_REGISTRY/idealens-web-svelte:latest
          docker push $ECR_REGISTRY/idealens-web-svelte:$GITHUB_SHA
          docker push $ECR_REGISTRY/idealens-web-svelte:latest

      - name: Resolve active frontend image URI
        run: |
          # DEPLOY_FRONTEND is a GitHub secret set to 'react' or 'svelte'
          if [ "${{ secrets.DEPLOY_FRONTEND }}" = "svelte" ]; then
            echo "WEB_IMAGE=$ECR_REGISTRY/idealens-web-svelte:$GITHUB_SHA" >> $GITHUB_ENV
          else
            echo "WEB_IMAGE=$ECR_REGISTRY/idealens-web-react:$GITHUB_SHA" >> $GITHUB_ENV
          fi

      - name: Run migrations
        run: |
          aws ecs run-task --cluster idealens \
            --task-definition idealens-api-migrate \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=ENABLED}" \
            --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
          # wait for task to complete and check exit code

      - name: Deploy api service
        run: aws ecs update-service --cluster idealens --service idealens-api --force-new-deployment

      - name: Deploy web service with selected frontend
        run: |
          # Register a new task definition revision with the selected frontend image,
          # then update the service to use it.
          NEW_TASK_DEF=$(aws ecs describe-task-definition --task-definition idealens-web \
            --query 'taskDefinition' | \
            jq --arg IMAGE "$WEB_IMAGE" \
              '.containerDefinitions[0].image = $IMAGE | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')
          NEW_TASK_ARN=$(aws ecs register-task-definition \
            --cli-input-json "$NEW_TASK_DEF" \
            --query 'taskDefinition.taskDefinitionArn' --output text)
          aws ecs update-service --cluster idealens --service idealens-web \
            --task-definition "$NEW_TASK_ARN"

      - name: Wait for stability
        run: |
          aws ecs wait services-stable --cluster idealens \
            --services idealens-api idealens-web
```

### GitHub Secrets required
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
ECR_REGISTRY         # <account_id>.dkr.ecr.us-east-1.amazonaws.com
DEPLOY_FRONTEND      # 'react' or 'svelte' — controls which frontend is live in production
```

---

## 10. Docker — Production Builds

### `apps/api/Dockerfile`
See `02_TODOS.md §5.6`.

### `apps/web-react/Dockerfile` — nginx serves static files, exposes port 80
```dockerfile
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json .
RUN npm ci
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`apps/web-react/nginx.conf` — SSE location block before `/api/`:
```nginx
server {
    listen 80;
    server_name _;

    location /api/chat {
        proxy_pass http://api:8000/api/chat;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /auth/ {
        proxy_pass http://api:8000/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri /index.html;
    }
}
```

### `apps/web-svelte/Dockerfile` — adapter-node Node server, exposes port 80
```dockerfile
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json .
RUN npm ci
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3001"]

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
ENV PUBLIC_API_URL=""
RUN npm run build

FROM node:20-alpine AS production
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json .
RUN npm ci --omit=dev
ENV PORT=80
ENV HOST=0.0.0.0
EXPOSE 80
CMD ["node", "build/index.js"]
# PORT=80 matches the React nginx container so sg-web and the ALB target group
# need no changes when switching frontends. PORT=3001 is local dev only.
```

In production, the ALB routes `/api/*` and `/auth/*` directly to the api target group via
routing rules (§5), so the SvelteKit Node container only receives frontend route requests —
no nginx sidecar needed.

---

## 11. Local Development

```bash
# Prerequisites: Docker Desktop, uv, Node 20+

# 1. Clone and setup
git clone <repo> && cd idealens
cp apps/api/.env.example apps/api/.env         # fill in JWT_SECRET and API_KEY_ENCRYPTION_KEY
cp apps/web-react/.env.example apps/web-react/.env
cp apps/web-svelte/.env.example apps/web-svelte/.env

# 2. Start all services — both frontends run simultaneously for side-by-side comparison
docker-compose up

# 3. Run migrations (first time only)
docker-compose exec api alembic upgrade head

# 4. Seed test data (optional)
docker-compose exec api python -m app.db.seed

# Access:
# React frontend:    http://localhost:3000
# SvelteKit frontend: http://localhost:3001
# API docs:          http://localhost:8000/docs
# Test user:         test@idealens.dev / testpass123 (after seeding)
```

To run only one frontend (saves resources during focused development on one implementation):
```bash
docker-compose up postgres api web-react    # React only
docker-compose up postgres api web-svelte   # SvelteKit only
```

---

## 12. Cost Summary

| Resource | Monthly (approx.) |
|---|---|
| ECS Fargate api (512/1024, 1 task) | ~$15 |
| ECS Fargate web (256/512, 1 task — one frontend) | ~$7 |
| RDS db.t3.micro | ~$15 |
| ALB base | ~$16 |
| ECR + transfer (3 repos, minimal storage) | ~$2 |
| Secrets Manager (3 secrets) | ~$1 |
| **Total** | **~$56/month** |

Identical to the original single-frontend estimate — only one web ECS task runs in
production regardless of which frontend is selected. Anthropic API costs are fully user-paid.

---

## 13. GCP (v2 — Placeholder)

When GCP support is added:
- Second Terraform workspace created in `infra/gcp/`
- Both frontend images and the api image pushed to GCP Artifact Registry by GitHub Actions
- `deploy.yml` gets a second parallel job: `deploy-gcp`
- `DEPLOY_FRONTEND` secret applies equally to the GCP deploy job
- Application code: zero changes
- Cloud Run replaces ECS; Cloud SQL replaces RDS; Secret Manager replaces Secrets Manager