variable "app_name" {
  type = string
}

variable "ssh_allowed_cidr" {
  type    = string
  default = "0.0.0.0/0"
}
