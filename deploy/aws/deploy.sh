#!/usr/bin/env bash
# Deploy to AWS — pushes images to ECR then deploys to App Runner.
#
# Prerequisites:
#   aws CLI configured (aws configure)
#   docker
#
# Required env vars:
#   APP_NAME                — used for ECR repo names and App Runner service names
#   APPRUNNER_ECR_ROLE_ARN  — IAM role ARN with AmazonEC2ContainerRegistryReadOnly
#
# Optional env vars:
#   AWS_REGION    — defaults to us-east-1
#   IMAGE_TAG     — defaults to git SHA

set -euo pipefail

APP_NAME=${APP_NAME:?Set APP_NAME (e.g. export APP_NAME=myapp)}
ROLE_ARN=${APPRUNNER_ECR_ROLE_ARN:?Set APPRUNNER_ECR_ROLE_ARN (IAM role with AmazonEC2ContainerRegistryReadOnly)}
AWS_REGION=${AWS_REGION:-us-east-1}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}

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

echo "==> Building and pushing backend"
docker build \
  --platform linux/amd64 \
  -t "$REGISTRY/$BACKEND_REPO:$IMAGE_TAG" \
  -t "$REGISTRY/$BACKEND_REPO:latest" \
  -f "$REPO_ROOT/infra/Dockerfile.backend" \
  "$REPO_ROOT/backend"
docker push "$REGISTRY/$BACKEND_REPO:$IMAGE_TAG"
docker push "$REGISTRY/$BACKEND_REPO:latest"

echo "==> Building and pushing frontend"
docker build \
  --platform linux/amd64 \
  -t "$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG" \
  -t "$REGISTRY/$FRONTEND_REPO:latest" \
  -f "$REPO_ROOT/infra/Dockerfile.frontend" \
  "$REPO_ROOT/frontend"
docker push "$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG"
docker push "$REGISTRY/$FRONTEND_REPO:latest"

echo ""
echo "==> Images pushed:"
echo "    $REGISTRY/$BACKEND_REPO:$IMAGE_TAG"
echo "    $REGISTRY/$FRONTEND_REPO:$IMAGE_TAG"
echo ""
echo "==> Deploying backend to App Runner"
if aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend']" \
     --output text | grep -q "$APP_NAME-backend"; then
  aws apprunner update-service \
    --service-arn "$(aws apprunner list-services \
      --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend'].ServiceArn" \
      --output text)" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$BACKEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"8000\",
          \"RuntimeEnvironmentVariables\": {
            \"APP_ENV\": \"production\"
          }
        }
      },
      \"AuthenticationConfiguration\": {
        \"AccessRoleArn\": \"$ROLE_ARN\"
      },
      \"AutoDeploymentsEnabled\": false
    }"
else
  aws apprunner create-service \
    --service-name "$APP_NAME-backend" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$BACKEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"8000\",
          \"RuntimeEnvironmentVariables\": {
            \"APP_ENV\": \"production\"
          }
        }
      },
      \"AuthenticationConfiguration\": {
        \"AccessRoleArn\": \"$ROLE_ARN\"
      },
      \"AutoDeploymentsEnabled\": false
    }" \
    --health-check-configuration "Protocol=HTTP,Path=/health"
fi

BACKEND_URL=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='$APP_NAME-backend'].ServiceUrl" \
  --output text)

echo "==> Deploying frontend to App Runner"
if aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend']" \
     --output text | grep -q "$APP_NAME-frontend"; then
  FRONTEND_ARN="$(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend'].ServiceArn" \
    --output text)"
  aws apprunner update-service \
    --service-arn "$FRONTEND_ARN" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"3000\",
          \"RuntimeEnvironmentVariables\": {
            \"PUBLIC_API_BASE_URL\": \"https://$BACKEND_URL\"
          }
        }
      },
      \"AuthenticationConfiguration\": {
        \"AccessRoleArn\": \"$ROLE_ARN\"
      },
      \"AutoDeploymentsEnabled\": false
    }"
else
  aws apprunner create-service \
    --service-name "$APP_NAME-frontend" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"3000\",
          \"RuntimeEnvironmentVariables\": {
            \"PUBLIC_API_BASE_URL\": \"https://$BACKEND_URL\"
          }
        }
      },
      \"AuthenticationConfiguration\": {
        \"AccessRoleArn\": \"$ROLE_ARN\"
      },
      \"AutoDeploymentsEnabled\": false
    }"
fi

# App Runner assigns a URL with a random hash (e.g. abc123.us-east-1.awsapprunner.com).
# The URL is only stable after the service is RUNNING, so ORIGIN is set in a second pass.
FRONTEND_URL=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend'].ServiceUrl" \
  --output text)

FRONTEND_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='$APP_NAME-frontend'].ServiceArn" \
  --output text)

echo "==> Setting ORIGIN on frontend (second pass)"
aws apprunner update-service \
  --service-arn "$FRONTEND_ARN" \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$REGISTRY/$FRONTEND_REPO:$IMAGE_TAG\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"3000\",
        \"RuntimeEnvironmentVariables\": {
          \"ORIGIN\": \"https://$FRONTEND_URL\",
          \"PUBLIC_API_BASE_URL\": \"https://$BACKEND_URL\"
        }
      }
    },
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"$ROLE_ARN\"
    },
    \"AutoDeploymentsEnabled\": false
  }"

echo ""
echo "Deployment complete."
echo "  Backend:  https://$BACKEND_URL"
echo "  Frontend: https://$FRONTEND_URL"
