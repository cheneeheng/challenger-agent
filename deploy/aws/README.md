# AWS Deployment — EC2 + S3/CloudFront

**Architecture:**

| Component | AWS resource | Details |
|---|---|---|
| API | EC2 t4g.small (ARM/Graviton2) | Docker + Nginx + Let's Encrypt; Elastic IP |
| Frontend | S3 + CloudFront | SvelteKit SPA (ssr=false); ACM cert; OAC origin |
| Database | RDS db.t3.micro | PostgreSQL 16; private subnet; encrypted |
| Images | ECR | ARM64 API image; lifecycle: last 10 kept |
| Secrets | Secrets Manager | DATABASE_URL, JWT_SECRET, API_KEY_ENCRYPTION_KEY |

**Cost estimate:** ~$26/month (EC2 $12, RDS $12, S3 $0.01, CloudFront $0.09, ECR $0.05, Secrets Manager $1.20)

---

## First deploy

### Step 0 — Prerequisites

```bash
brew install terraform awscli
# Configure AWS credentials
aws configure

# Create an EC2 key pair (needed by Terraform for var.ec2_key_pair_name)
aws ec2 create-key-pair \
  --key-name idealens-prod \
  --query KeyMaterial --output text > ~/.ssh/idealens-prod.pem
chmod 600 ~/.ssh/idealens-prod.pem
```

### Step 1 — Bootstrap Terraform state backend

Run once per AWS account. Creates the S3 bucket and DynamoDB table for remote state.

```bash
cd deploy/aws/terraform/bootstrap
terraform init
terraform apply

# Note the state_bucket output value, e.g. idealens-tf-state-123456789012
```

Edit `deploy/aws/terraform/backend.tf` and replace `REPLACE_WITH_ACCOUNT_ID` with
your account ID. Then:

```bash
cd deploy/aws/terraform
terraform init   # configures the S3 backend
```

### Step 2 — Configure variables

```bash
cp deploy/aws/terraform/terraform.tfvars.example deploy/aws/terraform/terraform.tfvars
# Fill in terraform.tfvars — domain, secrets, key pair name, etc.
# terraform.tfvars is gitignored.
```

Generate secrets:

```bash
openssl rand -hex 32                                          # jwt_secret
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # api_key_encryption_key
openssl rand -hex 16                                          # rds_password
```

### Step 3 — Apply Terraform

```bash
cd deploy/aws/terraform
terraform plan
terraform apply
```

Terraform creates EC2, RDS, ECR, S3, CloudFront, Secrets Manager entries, and a
GitHub Actions IAM user. Note the outputs — you'll need them in the next steps.

### Step 4 — DNS

Point your domains:
- `api.yourdomain.com` → EC2 Elastic IP (`terraform output ec2_elastic_ip`)
- `yourdomain.com` → CloudFront domain, or set up a CNAME/ALIAS in Route 53

Add the ACM DNS validation records (`terraform output acm_validation_records`)
to your DNS provider. CloudFront will not serve HTTPS until the cert validates.

### Step 5 — TLS on EC2 (Let's Encrypt)

After DNS propagates:

```bash
ssh -i ~/.ssh/idealens-prod.pem ec2-user@<elastic-ip>
sudo certbot --nginx -d api.yourdomain.com
```

Certbot rewrites the Nginx config to add HTTPS and sets up auto-renewal.

### Step 6 — Run database migrations

From inside the EC2 instance (or via SSM Session Manager):

```bash
# Via SSM (no SSH key needed)
aws ssm start-session --target <instance-id>

# On the EC2 instance:
docker exec -it $(docker ps -q) uv run alembic upgrade head
```

### Step 7 — Deploy

```bash
# Set required env vars (or add to root .env)
export APP_NAME=idealens
export ECR_REGISTRY=$(cd deploy/aws/terraform && terraform output -raw ecr_registry)
export EC2_INSTANCE_ID=$(cd deploy/aws/terraform && terraform output -raw ec2_instance_id)
export S3_BUCKET=$(cd deploy/aws/terraform && terraform output -raw s3_bucket)
export CF_DISTRIBUTION_ID=$(cd deploy/aws/terraform && terraform output -raw cloudfront_distribution_id)
export API_URL=https://api.idealens.dev

bash deploy/aws/deploy.sh
```

---

## Subsequent deploys

Only `deploy.sh` is needed — Terraform is only re-run when infrastructure changes.

```bash
bash deploy/aws/deploy.sh
```

---

## GitHub Actions secrets

After `terraform apply`, set these secrets in your GitHub repository:

```bash
terraform output -raw github_actions_access_key_id    # → AWS_ACCESS_KEY_ID
terraform output -raw github_actions_secret_access_key # → AWS_SECRET_ACCESS_KEY
terraform output -raw ec2_instance_id                 # → EC2_INSTANCE_ID
terraform output -raw ecr_registry                    # → ECR_REGISTRY
terraform output -raw s3_bucket                       # → S3_BUCKET
terraform output -raw cloudfront_distribution_id      # → CF_DISTRIBUTION_ID
```

Also set: `AWS_REGION`, `API_URL`.

---

## Terraform modules

| Module | Resources |
|---|---|
| `networking` | Default VPC data source, EC2 security group, RDS security group |
| `ecr` | ECR repository + lifecycle policy (keep last 10) |
| `rds` | RDS db.t3.micro PostgreSQL 16, DB subnet group |
| `secrets` | Secrets Manager entries for DATABASE_URL, JWT_SECRET, API_KEY_ENCRYPTION_KEY, FRONTEND_URLS_RAW |
| `ec2` | EC2 t4g.small (ARM64), Elastic IP, instance role (ECR + Secrets Manager + SSM), user data |
| `s3` | Private S3 bucket with versioning; bucket policy in root module |
| `cloudfront` | ACM cert (us-east-1), OAC, distribution with SPA 404 routing, cache policies |

Root `main.tf` also creates a GitHub Actions IAM user with least-privilege access
(ECR push, S3 sync, CloudFront invalidation, SSM send-command).

---

## Notes

**`PUBLIC_API_URL` is compiled at build time** by Vite. `deploy.sh` passes it as
an environment variable during `bun run build`. If you change the API domain,
re-run `deploy.sh` with the updated `API_URL`.

**SSE streaming**: the Nginx config written by EC2 user data sets
`proxy_buffering off` and `proxy_read_timeout 120s` on `/api/chat` so SSE tokens
reach the client without buffering delays.

**ARM64 images**: `deploy.sh` builds with `--platform linux/arm64` using Docker
Buildx. The EC2 instance type is `t4g.small` (Graviton2, ARM64). If you change
to an x86 instance type, also change the build platform and the `ec2_instance_type`
variable.

**Secrets rotation**: After rotating a secret, update it in Secrets Manager and
re-run the bootstrap script on EC2 to refresh `/opt/idealens/.env`:

```bash
aws ssm start-session --target <instance-id>
# Re-run the secrets pull section from user_data.sh.tpl
```

**App Runner alternative**: The original `setup-infra.sh` provisions an App
Runner-based stack (~$12/month cheaper but no persistent container for SSE).
See git history for the App Runner `deploy.sh` if needed.
