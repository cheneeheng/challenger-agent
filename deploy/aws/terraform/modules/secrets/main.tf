resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.app_name}/DATABASE_URL"
  recovery_window_in_days = 7
  tags                    = { Name = "${var.app_name}/DATABASE_URL" }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = var.database_url
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "${var.app_name}/JWT_SECRET"
  recovery_window_in_days = 7
  tags                    = { Name = "${var.app_name}/JWT_SECRET" }
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = var.jwt_secret
}

resource "aws_secretsmanager_secret" "api_key_encryption_key" {
  name                    = "${var.app_name}/API_KEY_ENCRYPTION_KEY"
  recovery_window_in_days = 7
  tags                    = { Name = "${var.app_name}/API_KEY_ENCRYPTION_KEY" }
}

resource "aws_secretsmanager_secret_version" "api_key_encryption_key" {
  secret_id     = aws_secretsmanager_secret.api_key_encryption_key.id
  secret_string = var.api_key_encryption_key
}

resource "aws_secretsmanager_secret" "frontend_urls" {
  name                    = "${var.app_name}/FRONTEND_URLS_RAW"
  recovery_window_in_days = 7
  tags                    = { Name = "${var.app_name}/FRONTEND_URLS_RAW" }
}

resource "aws_secretsmanager_secret_version" "frontend_urls" {
  secret_id     = aws_secretsmanager_secret.frontend_urls.id
  secret_string = var.frontend_urls_raw
}
