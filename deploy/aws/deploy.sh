#!/usr/bin/env bash
# Deploy to AWS — pushes images to ECR then deploys to App Runner.
#
# Prerequisites:
#   aws CLI configured (aws configure)
#   docker
#   Run deploy/aws/setup-infra.sh once before the first deploy.
#
# Required env vars:
#   APP_NAME                — used for ECR repo names and App Runner service names
#   APPRUNNER_ECR_ROLE_ARN  — IAM role ARN with AmazonEC2ContainerRegistryReadOnly
#   DATABASE_URL            — postgresql+asyncpg://user:pass@host:5432/db
#   JWT_SECRET              — min 32 chars; generate: openssl rand -hex 32
#   API_KEY_ENCRYPTION_KEY  — Fernet key; generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#
# Optional env vars:
#   AWS_REGION           — defaults to us-east-1
#   IMAGE_TAG            — defaults to git SHA
#   VPC_CONNECTOR_ARN    — attach backend to VPC so it can reach a private RDS instance
#   FRONTEND_URLS_RAW    — comma-separated CORS origins; defaults to the deployed frontend URL
#   SEED_ANTHROPIC_API_KEY — pre-seed an Anthropic key for the first user (optional)

set -euo pipefail

# Load .env from repo root if present. Explicit env exports take precedence
# because set -o allexport exports sourced vars but does not override existing ones.
REPO_ROOT=$(git rev-parse --show-toplevel)
if [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck source=/dev/null
  set -o allexport
  source <(grep -vE '^\s*(#|$)' "$REPO_ROOT/.env")
  set +o allexport
fi

APP_NAME=${APP_NAME:?Set APP_NAME}
ROLE_ARN=${APPRUNNER_ECR_ROLE_ARN:?Set APPRUNNER_ECR_ROLE_ARN}
DATABASE_URL=${DATABASE_URL:?Set DATABASE_URL}
JWT_SECRET=${JWT_SECRET:?Set JWT_SECRET}
API_KEY_ENCRYPTION_KEY=${API_KEY_ENCRYPTION_KEY:?Set API_KEY_ENCRYPTION_KEY}
AWS_REGION=${AWS_REGION:-us-east-1}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
VPC_CONNECTOR_ARN=${VPC_CONNECTOR_ARN:-}
SEED_ANTHROPIC_API_KEY=${SEED_ANTHROPIC_API_KEY:-}

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

BACKEND_REPO="$APP_NAME-backend"
FRONTEND_REPO="$APP_NAME-frontend"

REPO_ROOT=$(git rev-parse --show-toplevel)

echo "==> Logging in to ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Ensuring ECR repositories exist"
for repo in "$BACKEND_REPO" "$FRONTEND_REPO"; do
  aws ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" 2>/dev/null \
    || aws ecr create-repository --repository-name "$repo" --region "$AWS_REGION" \
         --image-scanning-configuration scanOnPush=true
done

# ---------------------------------------------------------------------------
# Backend — build, push, deploy first so we know the URL before building
# the frontend image (PUBLIC_API_URL is compiled into the bundle by Vite).
# ---------------------------------------------------------------------------
echo "==> Building and pushing backend"
docker build \
  --platform linux/amd64 \
  -t "$REGISTRY/$BACKEND_REPO:$IMAGE_TAG" \
  -t "$REGISTRY/$BACKEND_REPO:latest" \
  -f "$REPO_ROOT/infra/Dockerfile.backend" \
  "$REPO_ROOT/backend"
docker push "$REGISTRY/$BACKEND_REPO:$IMAGE_TAG"
docker push "$REGISTRY/$BACKEND_REPO:latest"

echo "==> Deploying backend to App Runner"

# Build the network-configuration fragment only when a VPC connector is set.
if [ -n "$VPC_CONNECTOR_ARN" ]; then
  NETWORK_CONFIG=", \"NetworkConfiguration\": { \"EgressConfiguration\": { \"EgressType\": \"VPC\", \"VpcConnectorArn\": \"$VPC_CONNECTOR_ARN\" } }"
else
  NETWORK_CONFIG=""
fi

BACKEND_ENV_VARS="\"ENVIRONMENT\": \"production\", \"DATABASE_URL\": \"$DATABASE_URL\", \"JWT_SECRET\": \"$JWT_SECRET\", \"API_KEY_ENCRYPTION_KEY\": \"$API_KEY_ENCRYPTION_KEY\", \"SEED_ANTHROPIC_API_KEY\": \"$SEED_ANTHROPIC_API_KEY\""

if aws apprunner list-services \
     --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend']" \
     --output text --region "$AWS_REGION" | grep -q "$APP_NAME-backend"; then
  aws apprunner update-service \
    --region "$AWS_REGION" \
    --service-arn "$(aws apprunner list-services \
      --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend'].ServiceArn" \
      --output text --region "$AWS_REGION")" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$BACKEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"8000\",
          \"RuntimeEnvironmentVariables\": { $BACKEND_ENV_VARS }
        }
      },
      \"AuthenticationConfiguration\": { \"AccessRoleArn\": \"$ROLE_ARN\" },
      \"AutoDeploymentsEnabled\": false
    }" \
    $([ -n "$NETWORK_CONFIG" ] && echo "--network-configuration {\"EgressConfiguration\":{\"EgressType\":\"VPC\",\"VpcConnectorArn\":\"$VPC_CONNECTOR_ARN\"}}")
else
  aws apprunner create-service \
    --region "$AWS_REGION" \
    --service-name "$APP_NAME-backend" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$BACKEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"8000\",
          \"RuntimeEnvironmentVariables\": { $BACKEND_ENV_VARS }
        }
      },
      \"AuthenticationConfiguration\": { \"AccessRoleArn\": \"$ROLE_ARN\" },
      \"AutoDeploymentsEnabled\": false
    }" \
    --health-check-configuration "Protocol=HTTP,Path=/health" \
    $([ -n "$VPC_CONNECTOR_ARN" ] && echo "--network-configuration {\"EgressConfiguration\":{\"EgressType\":\"VPC\",\"VpcConnectorArn\":\"$VPC_CONNECTOR_ARN\"}}")
fi

# Wait for the backend to be running so the URL is stable before building frontend.
echo "  Waiting for backend service to be running..."
aws apprunner wait service-running \
  --service-arn "$(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend'].ServiceArn" \
    --output text --region "$AWS_REGION")" \
  --region "$AWS_REGION"

BACKEND_URL=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend'].ServiceUrl" \
  --output text --region "$AWS_REGION")

# FRONTEND_URLS_RAW defaults to the deployed frontend URL; set it explicitly if
# you know the frontend URL in advance (e.g. custom domain).
FRONTEND_URLS_RAW=${FRONTEND_URLS_RAW:-"https://$BACKEND_URL"}

# Update backend now that we know FRONTEND_URLS_RAW.
aws apprunner update-service \
  --region "$AWS_REGION" \
  --service-arn "$(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend'].ServiceArn" \
    --output text --region "$AWS_REGION")" \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$REGISTRY/$BACKEND_REPO:$IMAGE_TAG\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\",
        \"RuntimeEnvironmentVariables\": {
          $BACKEND_ENV_VARS,
          \"FRONTEND_URLS_RAW\": \"$FRONTEND_URLS_RAW\"
        }
      }
    },
    \"AuthenticationConfiguration\": { \"AccessRoleArn\": \"$ROLE_ARN\" },
    \"AutoDeploymentsEnabled\": false
  }"

# ---------------------------------------------------------------------------
# Frontend — built after backend so PUBLIC_API_URL can be passed as a build
# arg and compiled into the bundle by Vite ($env/static/public).
# ---------------------------------------------------------------------------
echo "==> Building and pushing frontend"
docker build \
  --platform linux/amd64 \
  --build-arg PUBLIC_API_URL="https://$BACKEND_URL" \
  -t "$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG" \
  -t "$REGISTRY/$FRONTEND_REPO:latest" \
  -f "$REPO_ROOT/infra/Dockerfile.frontend" \
  "$REPO_ROOT/frontend"
docker push "$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG"
docker push "$REGISTRY/$FRONTEND_REPO:latest"

echo "==> Deploying frontend to App Runner"
if aws apprunner list-services \
     --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend']" \
     --output text --region "$AWS_REGION" | grep -q "$APP_NAME-frontend"; then
  aws apprunner update-service \
    --region "$AWS_REGION" \
    --service-arn "$(aws apprunner list-services \
      --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend'].ServiceArn" \
      --output text --region "$AWS_REGION")" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": { \"Port\": \"3000\" }
      },
      \"AuthenticationConfiguration\": { \"AccessRoleArn\": \"$ROLE_ARN\" },
      \"AutoDeploymentsEnabled\": false
    }"
else
  aws apprunner create-service \
    --region "$AWS_REGION" \
    --service-name "$APP_NAME-frontend" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": { \"Port\": \"3000\" }
      },
      \"AuthenticationConfiguration\": { \"AccessRoleArn\": \"$ROLE_ARN\" },
      \"AutoDeploymentsEnabled\": false
    }"
fi

# App Runner assigns a URL with a random hash (e.g. abc123.us-east-1.awsapprunner.com).
# The URL is only stable after the service is RUNNING, so ORIGIN is set in a second pass.
FRONTEND_URL=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend'].ServiceUrl" \
  --output text --region "$AWS_REGION")

FRONTEND_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend'].ServiceArn" \
  --output text --region "$AWS_REGION")

echo "==> Setting ORIGIN on frontend (second pass)"
aws apprunner update-service \
  --region "$AWS_REGION" \
  --service-arn "$FRONTEND_ARN" \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"3000\",
        \"RuntimeEnvironmentVariables\": {
          \"ORIGIN\": \"https://$FRONTEND_URL\"
        }
      }
    },
    \"AuthenticationConfiguration\": { \"AccessRoleArn\": \"$ROLE_ARN\" },
    \"AutoDeploymentsEnabled\": false
  }"

echo ""
echo "Deployment complete."
echo "  Backend:  https://$BACKEND_URL"
echo "  Frontend: https://$FRONTEND_URL"
