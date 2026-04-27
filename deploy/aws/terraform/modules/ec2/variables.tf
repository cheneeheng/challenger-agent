variable "app_name" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "instance_type" {
  type    = string
  default = "t4g.small"
}

variable "key_pair_name" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "ec2_sg_id" {
  type = string
}

variable "api_subdomain" {
  type        = string
  description = "API hostname used in Nginx server_name (e.g. api.idealens.dev)"
}

variable "ecr_registry" {
  type        = string
  description = "ECR registry hostname (account.dkr.ecr.region.amazonaws.com)"
}

variable "ecr_repo_url" {
  type        = string
  description = "Full ECR repository URL for the API image"
}

variable "secret_arns" {
  type        = list(string)
  description = "Secrets Manager ARNs the instance role is allowed to read"
}
