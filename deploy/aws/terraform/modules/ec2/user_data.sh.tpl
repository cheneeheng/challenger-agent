#!/bin/bash
set -euo pipefail

# ---- System packages -------------------------------------------------------
dnf install -y docker nginx certbot python3-certbot-nginx

systemctl enable --now docker
usermod -aG docker ec2-user

# Docker Compose plugin (ARM64 binary)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ---- App directory ---------------------------------------------------------
mkdir -p /opt/${app_name}

cat > /opt/${app_name}/docker-compose.yaml << 'COMPOSE'
services:
  api:
    image: ${ecr_repo_url}:latest
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    env_file: /opt/${app_name}/.env
    environment:
      ENVIRONMENT: production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
COMPOSE

# ---- Nginx -----------------------------------------------------------------
# HTTP-only config. Run certbot post-deploy to add HTTPS:
#   certbot --nginx -d ${api_subdomain}
cat > /etc/nginx/conf.d/${app_name}.conf << 'NGINX'
server {
    listen 80;
    server_name ${api_subdomain};

    # SSE endpoint — disable buffering so tokens stream to clients immediately
    location /api/chat {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Connection '';
        proxy_buffering    off;
        proxy_read_timeout 120s;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass       http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

# Remove default nginx config to avoid port conflict
rm -f /etc/nginx/conf.d/default.conf

systemctl enable --now nginx

# ---- Bootstrap .env from Secrets Manager -----------------------------------
# Populates /opt/${app_name}/.env on first boot using stored secrets.
# Re-run manually after rotating secrets.
aws secretsmanager get-secret-value \
  --region ${aws_region} \
  --secret-id ${app_name}/DATABASE_URL \
  --query SecretString --output text \
  | xargs -I{} echo "DATABASE_URL={}" \
  >> /opt/${app_name}/.env

aws secretsmanager get-secret-value \
  --region ${aws_region} \
  --secret-id ${app_name}/JWT_SECRET \
  --query SecretString --output text \
  | xargs -I{} echo "JWT_SECRET={}" \
  >> /opt/${app_name}/.env

aws secretsmanager get-secret-value \
  --region ${aws_region} \
  --secret-id ${app_name}/API_KEY_ENCRYPTION_KEY \
  --query SecretString --output text \
  | xargs -I{} echo "API_KEY_ENCRYPTION_KEY={}" \
  >> /opt/${app_name}/.env

aws secretsmanager get-secret-value \
  --region ${aws_region} \
  --secret-id ${app_name}/FRONTEND_URLS_RAW \
  --query SecretString --output text \
  | xargs -I{} echo "FRONTEND_URLS_RAW={}" \
  >> /opt/${app_name}/.env

chmod 600 /opt/${app_name}/.env

# ---- Pull and start API container ------------------------------------------
cd /opt/${app_name}
aws ecr get-login-password --region ${aws_region} \
  | docker login --username AWS --password-stdin ${ecr_registry}
docker compose pull
docker compose up -d
