variable "app_log_level" {
  default = "INFO"
}

variable "base_domain" {
  type    = string
  default = "losverd.es"
}

variable "cloud_run_subdomain" {
  type    = string
  default = "card"
}

variable "flask_env" {
  type    = string
  default = "production"
}

variable "gcp_project_editors" {
  type    = list(string)
  default = [
    "Jeff.Hogan1@gmail.com",
  ]
}

variable "gcp_project_id" {
  type = string
  default = "lv-digital-membership"
}

variable "gcp_region" {
  type    = string
  default = "us-central1"
}

variable "management_sql_user_password" {
  sensitive = true
  type      = string
}

variable "membership_squarespace_sku" {
  type    = string
  default = "SQ3671268"
}

variable "website_image" {
  type    = string
  default = "gcr.io/lv-digital-membership/website:bb39bec"
}

variable "worker_image" {
  type    = string
  default = "gcr.io/lv-digital-membership/worker:bb39bec"
}
