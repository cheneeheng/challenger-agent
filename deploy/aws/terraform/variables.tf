variable "aws_region" {
  description = "AWS region for all resources (ACM for CloudFront is always us-east-1)"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name — used as a prefix for all resource names"
  type        = string
  default     = "idealens"
}

variable "environment" {
  description = "Deployment environment tag"
  type        = string
  default     = "production"
}

# --- Domains ----------------------------------------------------------------

variable "domain_name" {
  description = "Primary domain for the frontend (e.g. idealens.dev)"
  type        = string
}

variable "api_subdomain" {
  description = "Full API domain used in Nginx config (e.g. api.idealens.dev)"
  type        = string
}

# --- Networking -------------------------------------------------------------

variable "ssh_allowed_cidr" {
  description = "CIDR allowed SSH access to EC2. Restrict to your IP in production."
  type        = string
  default     = "0.0.0.0/0"
}

# --- EC2 --------------------------------------------------------------------

variable "ec2_instance_type" {
  description = "EC2 instance type. t4g.* are ARM/Graviton — match Dockerfile.backend platform."
  type        = string
  default     = "t4g.small"
}

variable "ec2_key_pair_name" {
  description = "EC2 key pair name. Create it manually in the AWS console before applying."
  type        = string
}

# --- RDS --------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "idealens"
}

variable "rds_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "idealens"
}

variable "rds_password" {
  description = "PostgreSQL master password — store in a .tfvars file excluded from git"
  type        = string
  sensitive   = true
}

# --- Application secrets ----------------------------------------------------

variable "jwt_secret" {
  description = "JWT signing secret — min 32 chars. Generate: openssl rand -hex 32"
  type        = string
  sensitive   = true
}

variable "api_key_encryption_key" {
  description = "Fernet key for encrypting user API keys. Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
  type        = string
  sensitive   = true
}

variable "frontend_urls_raw" {
  description = "Comma-separated CORS allowed origins (e.g. https://idealens.dev)"
  type        = string
}
