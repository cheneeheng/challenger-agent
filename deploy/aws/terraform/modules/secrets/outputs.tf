output "database_url_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}

output "jwt_secret_arn" {
  value = aws_secretsmanager_secret.jwt_secret.arn
}

output "api_key_encryption_key_arn" {
  value = aws_secretsmanager_secret.api_key_encryption_key.arn
}

output "frontend_urls_arn" {
  value = aws_secretsmanager_secret.frontend_urls.arn
}

output "secret_arns" {
  value = [
    aws_secretsmanager_secret.database_url.arn,
    aws_secretsmanager_secret.jwt_secret.arn,
    aws_secretsmanager_secret.api_key_encryption_key.arn,
    aws_secretsmanager_secret.frontend_urls.arn,
  ]
  description = "All secret ARNs — granted to EC2 instance role"
}
