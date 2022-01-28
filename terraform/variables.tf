

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

variable "squarespace_api_key" {
  sensitive = true
}

variable "oauth_client_id" {
  sensitive = true
}

variable "oauth_client_secret" {
  sensitive = true
}

# resource "google_secret_manager_secret" "secret" {
#   secret_id = "secret"
#   replication {
#     automatic = true
#   }
# }

# resource "google_secret_manager_secret_version" "secret-version-data" {
#   secret      = google_secret_manager_secret.secret.name
#   secret_data = "secret-data"
# }

# resource "google_secret_manager_secret_iam_member" "secret-access" {
#   secret_id  = google_secret_manager_secret.secret.id
#   role       = "roles/secretmanager.secretAccessor"
#   member     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
#   depends_on = [google_secret_manager_secret.secret]
# }

# resource "google_cloud_run_service" "default" {
#   name     = "cloudrun-srv"
#   location = "us-central1"

#   template {
#     spec {
#       containers {
#         image = "gcr.io/cloudrun/hello"
#         volume_mounts {
#           name       = "a-volume"
#           mount_path = "/secrets"
#         }
#       }
#       volumes {
#         name = "a-volume"
#         secret {
#           secret_name  = google_secret_manager_secret.secret.secret_id
#           default_mode = 292 # 0444
#           items {
#             key  = "1"
#             path = "my-secret"
#             mode = 256 # 0400
#           }
#         }
#       }
#     }
#   }

#   metadata {
#     annotations = {
#       generated-by = "magic-modules"
#     }
#   }

#   traffic {
#     percent         = 100
#     latest_revision = true
#   }
#   autogenerate_revision_name = true

#   lifecycle {
#     ignore_changes = [
#       metadata.0.annotations,
#     ]
#   }

#   depends_on = [google_secret_manager_secret_version.secret-version-data]
# }
