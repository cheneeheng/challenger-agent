variable "app_name" {
  type = string
}

variable "domain_name" {
  type        = string
  description = "Frontend domain (e.g. idealens.dev) — must match the ACM cert"
}

variable "s3_regional_domain" {
  type        = string
  description = "S3 bucket regional domain name (from s3 module output)"
}

variable "s3_bucket_arn" {
  type        = string
  description = "S3 bucket ARN — used when constructing the bucket policy in root main.tf"
}
