variable "app_name" {
  type = string
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "api_key_encryption_key" {
  type      = string
  sensitive = true
}

variable "frontend_urls_raw" {
  type = string
}
