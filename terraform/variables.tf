

variable "apple_pass_certificate" {
  sensitive = true
}

variable "apple_pass_private_key_secret_name" {
  type    = string
  default = "apple_developer_private_key"
}

variable "apple_pass_private_key_password" {
  sensitive = true
}
# variable "gcp_billing_account_name" {}

variable "cloud_run_container_image" {
  type    = string
  default = "gcr.io/lv-digital-membership/member-card:latest"
}

variable "cloud_run_domain_name" {
  type    = string
  default = "card.losverd.es"
}

variable "flask_env" {
  type    = string
  default = "production"
}

variable "gcp_billing_account_id" {
  type = string
}

variable "gcp_project_editors" {
  type    = list(string)
  default = []
}

variable "gcp_project_id" {
  type = string
}

variable "gcp_project_name" {
  type = string
}

variable "gcp_project_owners" {
  type    = list(string)
  default = []
}

variable "gcp_region" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "membership_squarespace_sku" {
  type = string
}

variable "squarespace_api_key" {
  sensitive = true
}

variable "sendgrid_api_key" {
  sensitive = true
}

variable "oauth_client_id" {
  sensitive = true
}

variable "oauth_client_secret" {
  sensitive = true
}
