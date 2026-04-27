output "ec2_elastic_ip" {
  value       = module.ec2.elastic_ip
  description = "Point api.yourdomain.com A record here"
}

output "ec2_instance_id" {
  value       = module.ec2.instance_id
  description = "Set as EC2_INSTANCE_ID in GitHub Actions secrets"
}

output "ecr_registry" {
  value       = module.ecr.registry_url
  description = "Set as ECR_REGISTRY in GitHub Actions secrets"
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "s3_bucket" {
  value       = module.s3.bucket_id
  description = "Set as S3_BUCKET in GitHub Actions secrets"
}

output "cloudfront_distribution_id" {
  value       = module.cloudfront.distribution_id
  description = "Set as CF_DISTRIBUTION_ID in GitHub Actions secrets"
}

output "cloudfront_domain" {
  value       = module.cloudfront.domain_name
  description = "Temporary CloudFront URL — point CNAME here until custom domain validates"
}

output "rds_address" {
  value     = module.rds.address
  sensitive = true
}

output "github_actions_access_key_id" {
  value       = aws_iam_access_key.github_actions.id
  description = "Set as AWS_ACCESS_KEY_ID in GitHub Actions secrets"
}

output "github_actions_secret_access_key" {
  value       = aws_iam_access_key.github_actions.secret
  sensitive   = true
  description = "Set as AWS_SECRET_ACCESS_KEY in GitHub Actions secrets"
}

output "acm_validation_records" {
  value       = module.cloudfront.acm_validation_records
  description = "Add these DNS records to validate the ACM certificate"
}
