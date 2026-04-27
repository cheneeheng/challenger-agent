terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Fill in bucket after running bootstrap/main.tf (output: state_bucket).
  # Then run: terraform init -migrate-state
  backend "s3" {
    bucket         = "idealens-tf-state-REPLACE_WITH_ACCOUNT_ID"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "idealens-tf-locks"
    encrypt        = true
  }
}
