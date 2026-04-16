# AWS Deployment

Backend and frontend run as separate App Runner services. Images are stored in ECR.

---

## AWS resources

| Resource | Created by | Purpose |
|---|---|---|
| ECR repositories (×2) | `deploy.sh` | Store backend and frontend images |
| App Runner services (×2) | `deploy.sh` | Run backend (port 8000) and frontend (port 3000) |
| IAM role | You (once) | Lets App Runner pull images from ECR |
| RDS PostgreSQL 16 | `setup-infra.sh` | Managed database (private, in default VPC) |
| Security group | `setup-infra.sh` | Allows port 5432 from within the VPC |
| App Runner VPC connector | `setup-infra.sh` | Gives App Runner egress to the private RDS instance |
| Secrets Manager secrets | `setup-infra.sh` | Stores `DATABASE_URL`, `JWT_SECRET`, `API_KEY_ENCRYPTION_KEY` |

---

## IAM role (one-time, manual)

Create the role that allows App Runner to pull from ECR. You only do this once
per AWS account.

```bash
# 1. Create the role with the App Runner trust policy
aws iam create-role \
  --role-name AppRunnerECRRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "build.apprunner.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }'

# 2. Attach the managed policy
aws iam attach-role-policy \
  --role-name AppRunnerECRRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

# 3. Note the ARN — you'll need it as APPRUNNER_ECR_ROLE_ARN
aws iam get-role --role-name AppRunnerECRRole --query "Role.Arn" --output text
```

---

## First deploy

### Step 1 — Fill in `.env`

Both scripts read from the root `.env` automatically. Fill in the AWS Deploy
section (and the Backend section if you haven't already):

```bash
# Generate secrets
DB_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)
API_KEY_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

Then set these in `.env`:

```
APP_NAME=myapp
AWS_REGION=us-east-1
APPRUNNER_ECR_ROLE_ARN=arn:aws:iam::123456789012:role/AppRunnerECRRole
DB_PASSWORD=<generated above>
JWT_SECRET=<generated above>
API_KEY_ENCRYPTION_KEY=<generated above>
```

### Step 2 — Provision infrastructure

```bash
bash deploy/aws/setup-infra.sh
```

The script creates RDS, the VPC connector, and Secrets Manager entries, then
prints the `VPC_CONNECTOR_ARN` and `DATABASE_URL` to add to `.env`.

`setup-infra.sh` is idempotent — safe to re-run. Resources that already exist
are skipped.

### Step 3 — Run database migrations

App Runner services have no direct shell access. Connect to RDS from a machine
that has network access (EC2 in the same VPC, AWS Cloud Shell, or a temporary
SSH tunnel via an EC2 bastion):

```bash
# From a machine that can reach the RDS endpoint:
DATABASE_URL='postgresql+asyncpg://...' \
  cd backend && uv run alembic upgrade head
```

Alternatively, temporarily set `--publicly-accessible` on the RDS instance,
run migrations from your laptop, then disable public access.

### Step 4 — Deploy

```bash
bash deploy/aws/deploy.sh
```

---

## Subsequent deploys

Only `deploy.sh` is needed. Keep `.env` up to date and run:

```bash
bash deploy/aws/deploy.sh
```

---

## Secrets Manager

`setup-infra.sh` stores `DATABASE_URL`, `JWT_SECRET`, and `API_KEY_ENCRYPTION_KEY`
in Secrets Manager under `{APP_NAME}/DATABASE_URL` etc.

`deploy.sh` currently passes these as App Runner `RuntimeEnvironmentVariables`
(plaintext in the service config). For production, use App Runner's
`RuntimeEnvironmentSecrets` instead — it pulls values directly from Secrets
Manager and keeps them out of the service configuration API response:

```bash
# Retrieve an ARN for use in RuntimeEnvironmentSecrets
aws secretsmanager describe-secret \
  --secret-id "$APP_NAME/DATABASE_URL" \
  --query "ARN" --output text
```

Then replace the `RuntimeEnvironmentVariables` block in `deploy.sh` with:

```json
"RuntimeEnvironmentSecrets": {
  "DATABASE_URL":           "arn:aws:secretsmanager:...",
  "JWT_SECRET":             "arn:aws:secretsmanager:...",
  "API_KEY_ENCRYPTION_KEY": "arn:aws:secretsmanager:..."
}
```

The App Runner execution role will also need `secretsmanager:GetSecretValue`
added to its permissions.

---

## Notes

**`PUBLIC_API_URL` is compiled at build time**, not runtime. `deploy.sh`
builds the frontend image after the backend is deployed so it can pass the
correct backend URL as `--build-arg PUBLIC_API_URL`. If you add a custom
domain to the backend, set `PUBLIC_API_URL` to that domain so the URL stays
stable across redeploys.

**CORS**: `FRONTEND_URLS_RAW` on the backend defaults to the frontend App
Runner URL. If you add a custom domain, re-deploy the backend with
`FRONTEND_URLS_RAW` set to the custom domain.
