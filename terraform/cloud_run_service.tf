# cloudsql_instances = ["lv-digital-membership:us-central1:lv-digital-membership"]

# port = 8080
# capacity {
#   memory                     = 256
#   cpu_count                  = 1
#   max_requests_per_container = 10
#   request_timeout            = 15
# }

# auto_scaling {
#   max = 1
# }
resource "google_cloud_run_service" "digital_membership" {
  provider                   = google-beta
  name                       = "digital-membership"
  location                   = var.gcp_region
  autogenerate_revision_name = true

  traffic {
    percent         = 100
    latest_revision = true
  }

  template {

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale"      = "1"
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.digital_membership.connection_name
        "run.googleapis.com/client-name"        = "member-card"
      }
    }

    spec {
      service_account_name = google_service_account.digital_membership.email
      containers {
        image = var.cloud_run_container_image

        volume_mounts {
          name       = "apple_developer_key"
          mount_path = "/apple"
        }

        volume_mounts {
          name       = "secrets_json"
          mount_path = "/secrets"
        }

        env {
          name  = "DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"
          value = google_secret_manager_secret_version.digital_membership.name
        }
        env {
          name  = "FLASK_ENV"
          value = var.flask_env
        }
      }

      volumes {
        name = "apple_developer_key"
        secret {
          secret_name  = var.apple_pass_private_key_secret_name
          default_mode = 292 # 0444
          items {
            key  = "latest"
            path = "private.key"
            mode = 256 # 0400
          }
        }
      }

      volumes {
        name = "secrets_json"
        secret {
          secret_name  = google_secret_manager_secret.digital_membership.secret_id
          default_mode = 292 # 0444
          items {
            key  = "latest"
            path = "secrets.json"
            mode = 256 # 0400
          }
        }
      }
    }
  }
}

resource "google_cloud_run_domain_mapping" "digital_membership" {
  location = var.gcp_region
  name     = var.cloud_run_domain_name

  metadata {
    namespace = var.gcp_project_id
  }

  spec {
    route_name = google_cloud_run_service.digital_membership.name
  }
}
