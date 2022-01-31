locals {
  secret_version_parts           = split("/", google_secret_manager_secret_version.digital_membership.id)
  secret_version_key             = element(local.secret_version_parts, length(local.secret_version_parts) - 1)
  apple_key_secret_version_parts = split("/", data.google_secret_manager_secret_version.apple_private_key.id)
  apple_key_secret_version_key   = element(local.apple_key_secret_version_parts, length(local.apple_key_secret_version_parts) - 1)
}
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
        "autoscaling.knative.dev/minScale"      = "0"
        "autoscaling.knative.dev/maxScale"      = "1"
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.digital_membership.connection_name
        "run.googleapis.com/client-name"        = "member-card"
      }
    }

    spec {
      service_account_name = google_service_account.digital_membership.email
      containers {
        image = var.cloud_run_container_image

        env {
          name = "DIGITAL_MEMBERSHIP_SECRETS_JSON"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.digital_membership.secret_id
              key  = local.secret_version_key
            }
          }
        }

        env {
          name  = "DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"
          value = google_secret_manager_secret_version.digital_membership.name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME"
          value = google_sql_database_instance.digital_membership.connection_name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_DB_USERNAME"
          value = google_sql_user.service_accounts["website"].name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"
          value = google_sql_database.database.name
        }

        env {
          name  = "GCLOUD_PROJECT"
          value = var.gcp_project_id
        }

        env {
          name  = "FLASK_ENV"
          value = var.flask_env
        }

        env {
          name  = "LOG_LEVEL"
          value = "DEBUG"
        }

        ports {
          name = "http1"
          # protocol       = "TCP"
          container_port = "8080"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }

        volume_mounts {
          name       = "apple_developer_private_key"
          mount_path = "/secrets"
        }
      }

      volumes {
        name = "apple_developer_private_key"
        secret {
          secret_name  = data.google_secret_manager_secret.apple_private_key.secret_id
          default_mode = "0444" # 0444
          items {
            key  = local.apple_key_secret_version_key
            path = "apple-private.key"
            # mode = "0444" # 0444
            # mode = 256 # 0400
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
