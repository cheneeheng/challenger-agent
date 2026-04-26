# One-time bootstrap: creates the S3 bucket and DynamoDB table used as
# the Terraform remote state backend. Run this *before* configuring
# backend.tf and running terraform init in the parent directory.
#
# Usage:
#   cd deploy/aws/terraform/bootstrap
#   terraform init
#   terraform apply
#   # Note the state_bucket output, then fill it into ../backend.tf

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name prefix"
  type        = string
  default     = "idealens"
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.app_name}-tf-state-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${var.app_name}-tf-state" }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${var.app_name}-tf-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = { Name = "${var.app_name}-tf-locks" }
}

output "state_bucket" {
  value       = aws_s3_bucket.terraform_state.bucket
  description = "Copy this into deploy/aws/terraform/backend.tf as the bucket value"
}

output "lock_table" {
  value = aws_dynamodb_table.terraform_locks.name
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}
