provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ACM certificates for CloudFront must always be in us-east-1.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ---- Modules ---------------------------------------------------------------

module "networking" {
  source = "./modules/networking"

  app_name         = var.app_name
  ssh_allowed_cidr = var.ssh_allowed_cidr
}

module "ecr" {
  source   = "./modules/ecr"
  app_name = var.app_name
}

module "rds" {
  source = "./modules/rds"

  app_name          = var.app_name
  db_instance_class = var.rds_instance_class
  db_name           = var.rds_db_name
  db_username       = var.rds_username
  db_password       = var.rds_password
  subnet_ids        = module.networking.subnet_ids
  rds_sg_id         = module.networking.rds_sg_id
}

module "secrets" {
  source = "./modules/secrets"

  app_name               = var.app_name
  jwt_secret             = var.jwt_secret
  api_key_encryption_key = var.api_key_encryption_key
  frontend_urls_raw      = var.frontend_urls_raw

  # DATABASE_URL is constructed from RDS outputs so Terraform knows the endpoint before writing.
  database_url = "postgresql+asyncpg://${var.rds_username}:${var.rds_password}@${module.rds.address}:${module.rds.port}/${module.rds.db_name}"

  depends_on = [module.rds]
}

module "ec2" {
  source = "./modules/ec2"

  app_name      = var.app_name
  aws_region    = var.aws_region
  instance_type = var.ec2_instance_type
  key_pair_name = var.ec2_key_pair_name
  subnet_id     = module.networking.subnet_ids[0]
  ec2_sg_id     = module.networking.ec2_sg_id
  api_subdomain = var.api_subdomain
  ecr_registry  = module.ecr.registry_url
  ecr_repo_url  = module.ecr.repository_url
  secret_arns   = module.secrets.secret_arns

  depends_on = [module.secrets]
}

module "s3" {
  source   = "./modules/s3"
  app_name = var.app_name
}

module "cloudfront" {
  source = "./modules/cloudfront"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  app_name           = var.app_name
  domain_name        = var.domain_name
  s3_regional_domain = module.s3.regional_domain_name
  s3_bucket_arn      = module.s3.bucket_arn
}

# ---- S3 bucket policy (OAC: CloudFront only) ------------------------------
# Placed in root to avoid a circular dependency between s3 and cloudfront modules.

resource "aws_s3_bucket_policy" "frontend" {
  bucket = module.s3.bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontServicePrincipal"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${module.s3.bucket_arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = module.cloudfront.distribution_arn
        }
      }
    }]
  })
}

# ---- GitHub Actions IAM user ----------------------------------------------
# Used by CI/CD to push images, sync S3, and trigger SSM deploys.

data "aws_caller_identity" "current" {}

resource "aws_iam_user" "github_actions" {
  name = "${var.app_name}-github-actions"
  tags = { Name = "${var.app_name}-github-actions" }
}

resource "aws_iam_access_key" "github_actions" {
  user = aws_iam_user.github_actions.name
}

data "aws_iam_policy_document" "github_actions" {
  # ECR: push images
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = ["*"]
  }

  # S3: sync frontend build
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObject",
    ]
    resources = ["${module.s3.bucket_arn}/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [module.s3.bucket_arn]
  }

  # CloudFront: invalidate after S3 sync
  statement {
    effect    = "Allow"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = ["arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${module.cloudfront.distribution_id}"]
  }

  # SSM: SendCommand requires both the document and instance ARN as resources
  statement {
    effect  = "Allow"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
      "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${module.ec2.instance_id}",
    ]
  }

  # GetCommandInvocation and DescribeInstanceInformation have no resource ARN
  statement {
    effect = "Allow"
    actions = [
      "ssm:GetCommandInvocation",
      "ssm:DescribeInstanceInformation",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_user_policy" "github_actions" {
  name   = "${var.app_name}-github-actions"
  user   = aws_iam_user.github_actions.name
  policy = data.aws_iam_policy_document.github_actions.json
}
