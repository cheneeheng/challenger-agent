#!/usr/bin/env bash
# One-time AWS infrastructure setup — run before the first deploy.
# Creates: RDS PostgreSQL 16, App Runner VPC connector, Secrets Manager secrets.
# Safe to re-run — all steps check for existing resources before creating.
#
# Prerequisites:
#   aws CLI configured with an IAM user/role that has:
#     AmazonRDSFullAccess, AmazonVPCFullAccess,
#     AWSAppRunnerFullAccess, SecretsManagerReadWrite
#
# Required env vars:
#   APP_NAME               — used as prefix for all resource names
#   DB_PASSWORD            — master password for the RDS instance
#   JWT_SECRET             — generate: openssl rand -hex 32
#   API_KEY_ENCRYPTION_KEY — generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#
# Optional env vars:
#   AWS_REGION   — defaults to us-east-1
#   DB_INSTANCE_CLASS — defaults to db.t3.micro

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
DB_PASSWORD=${DB_PASSWORD:?Set DB_PASSWORD}
JWT_SECRET=${JWT_SECRET:?Set JWT_SECRET}
API_KEY_ENCRYPTION_KEY=${API_KEY_ENCRYPTION_KEY:?Set API_KEY_ENCRYPTION_KEY}
AWS_REGION=${AWS_REGION:-us-east-1}
DB_INSTANCE_CLASS=${DB_INSTANCE_CLASS:-db.t3.micro}

# Sanitise: hyphens are not valid in PostgreSQL identifiers
DB_IDENTIFIER="${APP_NAME}-postgres"
DB_USERNAME="${APP_NAME//-/_}"
DB_NAME="${APP_NAME//-/_}"

# ---------------------------------------------------------------------------
# 1. Default VPC
# ---------------------------------------------------------------------------
echo "==> Resolving default VPC"
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region "$AWS_REGION")

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
  echo "No default VPC found in $AWS_REGION."
  echo "Create one with: aws ec2 create-default-vpc --region $AWS_REGION"
  exit 1
fi
echo "  VPC: $VPC_ID"

VPC_CIDR=$(aws ec2 describe-vpcs \
  --vpc-ids "$VPC_ID" \
  --query "Vpcs[0].CidrBlock" \
  --output text \
  --region "$AWS_REGION")

# Collect all subnet IDs as a bash array
readarray -t SUBNET_ARRAY < <(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[*].SubnetId" \
  --output text \
  --region "$AWS_REGION" | tr '\t' '\n')

echo "  Subnets: ${SUBNET_ARRAY[*]}"

# ---------------------------------------------------------------------------
# 2. Security group for RDS (allow 5432 from within the VPC)
# ---------------------------------------------------------------------------
echo "==> Security group"
SG_NAME="${APP_NAME}-rds-sg"
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text \
  --region "$AWS_REGION")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "RDS PostgreSQL access for $APP_NAME" \
    --vpc-id "$VPC_ID" \
    --query "GroupId" \
    --output text \
    --region "$AWS_REGION")
  aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 5432 \
    --cidr "$VPC_CIDR" \
    --region "$AWS_REGION" > /dev/null
  echo "  Created: $SG_ID"
else
  echo "  Exists:  $SG_ID"
fi

# ---------------------------------------------------------------------------
# 3. RDS subnet group
# ---------------------------------------------------------------------------
echo "==> RDS subnet group"
SUBNET_GROUP_NAME="${APP_NAME}-subnet-group"
if ! aws rds describe-db-subnet-groups \
       --db-subnet-group-name "$SUBNET_GROUP_NAME" \
       --region "$AWS_REGION" &>/dev/null; then
  aws rds create-db-subnet-group \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" \
    --db-subnet-group-description "Subnet group for $APP_NAME" \
    --subnet-ids "${SUBNET_ARRAY[@]}" \
    --region "$AWS_REGION" > /dev/null
  echo "  Created: $SUBNET_GROUP_NAME"
else
  echo "  Exists:  $SUBNET_GROUP_NAME"
fi

# ---------------------------------------------------------------------------
# 4. RDS PostgreSQL 16 instance
# ---------------------------------------------------------------------------
echo "==> RDS instance"
if ! aws rds describe-db-instances \
       --db-instance-identifier "$DB_IDENTIFIER" \
       --region "$AWS_REGION" &>/dev/null; then
  echo "  Creating (this takes ~5 minutes)..."
  aws rds create-db-instance \
    --db-instance-identifier "$DB_IDENTIFIER" \
    --db-instance-class "$DB_INSTANCE_CLASS" \
    --engine postgres \
    --engine-version "16" \
    --master-username "$DB_USERNAME" \
    --master-user-password "$DB_PASSWORD" \
    --db-name "$DB_NAME" \
    --allocated-storage 20 \
    --storage-type gp2 \
    --no-multi-az \
    --no-publicly-accessible \
    --vpc-security-group-ids "$SG_ID" \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" \
    --backup-retention-period 7 \
    --region "$AWS_REGION" > /dev/null
fi

echo "  Waiting for RDS to become available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_IDENTIFIER" \
  --region "$AWS_REGION"

DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_IDENTIFIER" \
  --query "DBInstances[0].Endpoint.Address" \
  --output text \
  --region "$AWS_REGION")
echo "  Endpoint: $DB_HOST"

DATABASE_URL="postgresql+asyncpg://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"

# ---------------------------------------------------------------------------
# 5. App Runner VPC connector (lets App Runner reach the private RDS)
# ---------------------------------------------------------------------------
echo "==> App Runner VPC connector"
CONNECTOR_NAME="${APP_NAME}-vpc-connector"
CONNECTOR_ARN=$(aws apprunner list-vpc-connectors \
  --query "VpcConnectors[?VpcConnectorName=='$CONNECTOR_NAME' && Status=='ACTIVE'].VpcConnectorArn | [0]" \
  --output text \
  --region "$AWS_REGION")

if [ "$CONNECTOR_ARN" = "None" ] || [ -z "$CONNECTOR_ARN" ]; then
  CONNECTOR_ARN=$(aws apprunner create-vpc-connector \
    --vpc-connector-name "$CONNECTOR_NAME" \
    --subnets "${SUBNET_ARRAY[@]}" \
    --security-groups "$SG_ID" \
    --query "VpcConnector.VpcConnectorArn" \
    --output text \
    --region "$AWS_REGION")
  echo "  Created: $CONNECTOR_ARN"
else
  echo "  Exists:  $CONNECTOR_ARN"
fi

# ---------------------------------------------------------------------------
# 6. Secrets Manager — store secrets the backend needs at runtime
# ---------------------------------------------------------------------------
echo "==> Secrets Manager"
store_secret() {
  local key="$1" value="$2"
  local full_name="${APP_NAME}/${key}"
  if aws secretsmanager describe-secret \
       --secret-id "$full_name" \
       --region "$AWS_REGION" &>/dev/null; then
    aws secretsmanager put-secret-value \
      --secret-id "$full_name" \
      --secret-string "$value" \
      --region "$AWS_REGION" > /dev/null
    echo "  Updated: $full_name"
  else
    aws secretsmanager create-secret \
      --name "$full_name" \
      --secret-string "$value" \
      --region "$AWS_REGION" > /dev/null
    echo "  Created: $full_name"
  fi
}

store_secret "DATABASE_URL"            "$DATABASE_URL"
store_secret "JWT_SECRET"              "$JWT_SECRET"
store_secret "API_KEY_ENCRYPTION_KEY"  "$API_KEY_ENCRYPTION_KEY"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Infrastructure ready."
echo ""
echo "Next steps:"
echo ""
echo "  1. Run Alembic migrations (from a machine with network access to RDS, or a"
echo "     temporary EC2/Cloud Shell in the same VPC):"
echo ""
echo "       DATABASE_URL='$DATABASE_URL' \\"
echo "         cd backend && uv run alembic upgrade head"
echo ""
echo "  2. Export before running deploy.sh:"
echo ""
echo "       export VPC_CONNECTOR_ARN='$CONNECTOR_ARN'"
echo "       export DATABASE_URL='$DATABASE_URL'"
echo "       export JWT_SECRET='$JWT_SECRET'"
echo "       export API_KEY_ENCRYPTION_KEY='$API_KEY_ENCRYPTION_KEY'"
echo ""
echo "  3. Run deploy.sh."
