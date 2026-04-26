output "repository_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "Full ECR repository URL (registry/repo)"
}

output "registry_url" {
  value       = replace(aws_ecr_repository.api.repository_url, "/${var.app_name}-api", "")
  description = "ECR registry hostname (account.dkr.ecr.region.amazonaws.com)"
}
