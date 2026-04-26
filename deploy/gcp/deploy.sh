#!/usr/bin/env bash
# Deploy to GCP — pushes images to Artifact Registry then deploys to Cloud Run.
#
# Prerequisites:
#   gcloud CLI authenticated (gcloud auth login && gcloud auth configure-docker)
#   docker
#   Artifact Registry API enabled: gcloud services enable artifactregistry.googleapis.com
#   Cloud Run API enabled:          gcloud services enable run.googleapis.com
#
# Required env vars:
#   GCP_PROJECT   — GCP project ID
#   APP_NAME      — used for Artifact Registry repo and Cloud Run service names
#
# Optional env vars:
#   GCP_REGION    — defaults to us-central1
#   IMAGE_TAG     — defaults to git SHA

set -euo pipefail

GCP_PROJECT=${GCP_PROJECT:?Set GCP_PROJECT (e.g. export GCP_PROJECT=my-gcp-project)}
APP_NAME=${APP_NAME:?Set APP_NAME (e.g. export APP_NAME=myapp)}
GCP_REGION=${GCP_REGION:-us-central1}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}

REGISTRY="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT/$APP_NAME"

REPO_ROOT=$(git rev-parse --show-toplevel)

echo "==> Configuring Docker auth for Artifact Registry"
gcloud auth configure-docker "$GCP_REGION-docker.pkg.dev" --quiet

echo "==> Ensuring Artifact Registry repository exists"
gcloud artifacts repositories describe "$APP_NAME" \
  --location="$GCP_REGION" --project="$GCP_PROJECT" 2>/dev/null \
  || gcloud artifacts repositories create "$APP_NAME" \
       --repository-format=docker \
       --location="$GCP_REGION" \
       --project="$GCP_PROJECT"

echo "==> Building and pushing backend"
docker build \
  --platform linux/amd64 \
  -t "$REGISTRY/backend:$IMAGE_TAG" \
  -t "$REGISTRY/backend:latest" \
  -f "$REPO_ROOT/deploy/Dockerfile.backend" \
  "$REPO_ROOT/backend"
docker push "$REGISTRY/backend:$IMAGE_TAG"
docker push "$REGISTRY/backend:latest"

echo "==> Building and pushing frontend"
docker build \
  --platform linux/amd64 \
  -t "$REGISTRY/frontend:$IMAGE_TAG" \
  -t "$REGISTRY/frontend:latest" \
  -f "$REPO_ROOT/deploy/Dockerfile.frontend" \
  "$REPO_ROOT/frontend"
docker push "$REGISTRY/frontend:$IMAGE_TAG"
docker push "$REGISTRY/frontend:latest"

echo "==> Deploying backend to Cloud Run"
gcloud run deploy "$APP_NAME-backend" \
  --image "$REGISTRY/backend:$IMAGE_TAG" \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --port 8000 \
  --allow-unauthenticated \
  --set-env-vars "APP_ENV=production"

BACKEND_URL=$(gcloud run services describe "$APP_NAME-backend" \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --format "value(status.url)")

echo "==> Deploying frontend to Cloud Run"
gcloud run deploy "$APP_NAME-frontend" \
  --image "$REGISTRY/frontend:$IMAGE_TAG" \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --port 3000 \
  --allow-unauthenticated \
  --set-env-vars "PUBLIC_API_URL=$BACKEND_URL"

FRONTEND_URL=$(gcloud run services describe "$APP_NAME-frontend" \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --format "value(status.url)")

# Set ORIGIN now that we know the frontend URL
gcloud run services update "$APP_NAME-frontend" \
  --platform managed \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --update-env-vars "ORIGIN=$FRONTEND_URL"

echo ""
echo "Deployment complete."
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
