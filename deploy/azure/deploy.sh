#!/usr/bin/env bash
# Deploy to Azure — pushes images to ACR then deploys to Container Apps.
#
# Prerequisites:
#   az CLI authenticated (az login)
#   docker
#
# Required env vars:
#   RESOURCE_GROUP  — Azure resource group (created if it doesn't exist)
#   APP_NAME        — used for ACR name, Container Apps names (alphanumeric only)
#
# Optional env vars:
#   LOCATION        — defaults to eastus
#   IMAGE_TAG       — defaults to git SHA

set -euo pipefail

RESOURCE_GROUP=${RESOURCE_GROUP:?Set RESOURCE_GROUP (e.g. export RESOURCE_GROUP=myapp-rg)}
APP_NAME=${APP_NAME:?Set APP_NAME (e.g. export APP_NAME=myapp)}
LOCATION=${LOCATION:-eastus}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}

# ACR names must be globally unique, alphanumeric, 5-50 chars
ACR_NAME="${APP_NAME}acr"
ENVIRONMENT_NAME="$APP_NAME-env"

REPO_ROOT=$(git rev-parse --show-toplevel)

echo "==> Ensuring resource group exists"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Ensuring Azure Container Registry exists"
az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null \
  || az acr create \
       --name "$ACR_NAME" \
       --resource-group "$RESOURCE_GROUP" \
       --sku Basic \
       --admin-enabled true

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)

echo "==> Logging in to ACR"
az acr login --name "$ACR_NAME"

echo "==> Building and pushing backend"
docker build \
  --platform linux/amd64 \
  -t "$ACR_LOGIN_SERVER/backend:$IMAGE_TAG" \
  -t "$ACR_LOGIN_SERVER/backend:latest" \
  -f "$REPO_ROOT/infra/Dockerfile.backend" \
  "$REPO_ROOT/backend"
docker push "$ACR_LOGIN_SERVER/backend:$IMAGE_TAG"
docker push "$ACR_LOGIN_SERVER/backend:latest"

echo "==> Building and pushing frontend"
docker build \
  --platform linux/amd64 \
  -t "$ACR_LOGIN_SERVER/frontend:$IMAGE_TAG" \
  -t "$ACR_LOGIN_SERVER/frontend:latest" \
  -f "$REPO_ROOT/infra/Dockerfile.frontend" \
  "$REPO_ROOT/frontend"
docker push "$ACR_LOGIN_SERVER/frontend:$IMAGE_TAG"
docker push "$ACR_LOGIN_SERVER/frontend:latest"

ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value --output tsv)

echo "==> Ensuring Container Apps environment exists"
az containerapp env show --name "$ENVIRONMENT_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null \
  || az containerapp env create \
       --name "$ENVIRONMENT_NAME" \
       --resource-group "$RESOURCE_GROUP" \
       --location "$LOCATION"

echo "==> Deploying backend"
if az containerapp show --name "$APP_NAME-backend" --resource-group "$RESOURCE_GROUP" 2>/dev/null; then
  az containerapp update \
    --name "$APP_NAME-backend" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/backend:$IMAGE_TAG"
else
  az containerapp create \
    --name "$APP_NAME-backend" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENVIRONMENT_NAME" \
    --image "$ACR_LOGIN_SERVER/backend:$IMAGE_TAG" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port 8000 \
    --ingress external \
    --env-vars "APP_ENV=production"
fi

BACKEND_FQDN=$(az containerapp show \
  --name "$APP_NAME-backend" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo "==> Deploying frontend"
if az containerapp show --name "$APP_NAME-frontend" --resource-group "$RESOURCE_GROUP" 2>/dev/null; then
  az containerapp update \
    --name "$APP_NAME-frontend" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/frontend:$IMAGE_TAG"
else
  az containerapp create \
    --name "$APP_NAME-frontend" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENVIRONMENT_NAME" \
    --image "$ACR_LOGIN_SERVER/frontend:$IMAGE_TAG" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port 3000 \
    --ingress external \
    --env-vars "PUBLIC_API_BASE_URL=https://$BACKEND_FQDN"
fi

# The FQDN is assigned immediately after create/update. Set ORIGIN in a second
# pass so it always reflects the real URL rather than a guessed value.
FRONTEND_FQDN=$(az containerapp show \
  --name "$APP_NAME-frontend" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo "==> Setting ORIGIN on frontend (second pass)"
az containerapp update \
  --name "$APP_NAME-frontend" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "ORIGIN=https://$FRONTEND_FQDN"

echo ""
echo "Deployment complete."
echo "  Backend:  https://$BACKEND_FQDN"
echo "  Frontend: https://$FRONTEND_FQDN"
