output "distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}

output "distribution_arn" {
  value       = aws_cloudfront_distribution.frontend.arn
  description = "Used in the S3 bucket policy condition (AWS:SourceArn)"
}

output "domain_name" {
  value       = aws_cloudfront_distribution.frontend.domain_name
  description = "CloudFront domain — point your DNS CNAME here until custom domain is validated"
}

output "oac_id" {
  value = aws_cloudfront_origin_access_control.frontend.id
}
