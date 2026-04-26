#!/usr/bin/env bash
# Deploy to AWS — builds ARM64 API image, pushes to ECR, updates EC2 via SSM,
# builds frontend SPA, syncs to S3, and invalidates CloudFront.
#
# Prerequisites:
#   aws CLI configured, docker with buildx (buildx build --platform linux/arm64)
#   bun installed locally for frontend build
#   Terraform applied: EC2 instance, S3 bucket, and CloudFront distribution exist
#   terraform output values stored in GitHub Actions secrets (see README)
#
# Required env vars:
#   APP_NAME              — matches var.app_name in terraform.tfvars
#   ECR_REGISTRY          — terraform output: ecr_registry
#   EC2_INSTANCE_ID       — terraform output: ec2_instance_id
#   S3_BUCKET             — terraform output: s3_bucket
#   CF_DISTRIBUTION_ID    — terraform output: cloudfront_distribution_id
#   API_URL               — public API URL e.g. https://api.idealens.dev
#
# Optional env vars:
#   AWS_REGION            — defaults to us-east-1
#   IMAGE_TAG             — defaults to git short SHA

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)

# Load root .env if present; explicit exports take precedence.
if [ -f "$REPO_ROOT/.env" ]; then
  set -o allexport
  # shellcheck source=/dev/null
  source <(grep -vE '^\s*(#|$)' "$REPO_ROOT/.env")
  set +o allexport
fi

APP_NAME=${APP_NAME:?Set APP_NAME}
ECR_REGISTRY=${ECR_REGISTRY:?Set ECR_REGISTRY}
EC2_INSTANCE_ID=${EC2_INSTANCE_ID:?Set EC2_INSTANCE_ID}
S3_BUCKET=${S3_BUCKET:?Set S3_BUCKET}
CF_DISTRIBUTION_ID=${CF_DISTRIBUTION_ID:?Set CF_DISTRIBUTION_ID}
API_URL=${API_URL:?Set API_URL}

AWS_REGION=${AWS_REGION:-us-east-1}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}

ECR_REPO="${ECR_REGISTRY}/${APP_NAME}-api"

# ---------------------------------------------------------------------------
# Backend — build ARM64 image and push to ECR
# ---------------------------------------------------------------------------
echo "==> Logging in to ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "==> Building backend (linux/arm64)"
docker buildx build \
  --platform linux/arm64 \
  -t "${ECR_REPO}:${IMAGE_TAG}" \
  -t "${ECR_REPO}:latest" \
  -f "$REPO_ROOT/deploy/Dockerfile.backend" \
  --push \
  "$REPO_ROOT/backend"

# ---------------------------------------------------------------------------
# Backend deploy — SSM RunCommand on EC2 (no SSH keys required)
# ---------------------------------------------------------------------------
echo "==> Deploying backend via SSM"

COMMAND_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$EC2_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[
    \"aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}\",
    \"cd /opt/${APP_NAME} && docker compose pull\",
    \"cd /opt/${APP_NAME} && docker compose up -d --remove-orphans\",
    \"docker image prune -f\"
  ]" \
  --output text \
  --query "Command.CommandId")

echo "  SSM command: $COMMAND_ID — waiting..."

# Poll until the command finishes (timeout after ~5 min)
for i in $(seq 1 30); do
  STATUS=$(aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$COMMAND_ID" \
    --instance-id "$EC2_INSTANCE_ID" \
    --query "Status" --output text 2>/dev/null || echo "Pending")
  case "$STATUS" in
    Success)
      echo "  EC2 deploy succeeded"
      break
      ;;
    Failed|Cancelled|TimedOut|Undeliverable)
      echo "  EC2 deploy failed (status: $STATUS)"
      aws ssm get-command-invocation \
        --region "$AWS_REGION" \
        --command-id "$COMMAND_ID" \
        --instance-id "$EC2_INSTANCE_ID" \
        --query "StandardErrorContent" --output text
      exit 1
      ;;
    *)
      echo "  Status: $STATUS — waiting 10s..."
      sleep 10
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Frontend — build SPA with PUBLIC_API_URL baked in, sync to S3
# ---------------------------------------------------------------------------
echo "==> Building frontend SPA (PUBLIC_API_URL=$API_URL)"
cd "$REPO_ROOT/frontend"
PUBLIC_API_URL="$API_URL" bun run build

echo "==> Syncing Vite assets to S3 (immutable cache)"
# Vite assets have content-hashed filenames — safe to cache for 1 year
aws s3 sync dist/ "s3://${S3_BUCKET}/" \
  --delete \
  --exclude "index.html" \
  --cache-control "public, max-age=31536000, immutable" \
  --region "$AWS_REGION"

echo "==> Uploading index.html (no-cache)"
# index.html must not be cached — it references hashed asset URLs
aws s3 cp dist/index.html "s3://${S3_BUCKET}/index.html" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --region "$AWS_REGION"

echo "==> Invalidating CloudFront"
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$CF_DISTRIBUTION_ID" \
  --paths "/*" \
  --query "Invalidation.Id" --output text)

echo ""
echo "Deploy complete."
echo "  Backend:  ${API_URL}/health"
echo "  Frontend: check CloudFront domain (terraform output cloudfront_domain)"
echo "  CF invalidation: $INVALIDATION_ID"
