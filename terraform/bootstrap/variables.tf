variable "gcp_billing_account_id" {
  type    = string
  default = "019767-2A54C9-AE07C6"
}

variable "app_secret_data" {
  sensitive = true
  type      = string
}

variable "gcp_project_id" {
  type    = string
  default = "lv-digital-membership"
}

variable "gcp_project_name" {
  type    = string
  default = "LV Digital Membership Cards!"
}

variable "gcp_region" {
  type    = string
  default = "us-central1"
}

variable "github_repo" {
  type    = string
  default = "los-verdes/digital-membership"
}
