locals {
  cloud_run_domain_name = "${var.cloud_run_subdomain}.${var.base_domain}"

  cloud_run_services = {
    "website" = {
      image                   = var.website_image
      service_account_name    = google_service_account.digital_membership["website"].email
      mount_apple_private_key = true
      memory_mb               = "512"
      min_scale               = "0"
      invokers                = ["allUsers"]
    }
    "worker" = {
      image                   = var.worker_image
      service_account_name    = google_service_account.digital_membership["worker"].email
      mount_apple_private_key = true
      min_scale               = "0"
      memory_mb               = "512"
      invokers                = ["serviceAccount:${google_service_account.digital_membership["worker-pubsub-invoker"].email}"]
    }
  }

  secret_version_parts           = split("/", data.terraform_remote_state.bootstrap.outputs.secret_id)
  secret_version_key             = element(local.secret_version_parts, length(local.secret_version_parts) - 1)
  apple_key_secret_version_parts = split("/", data.google_secret_manager_secret_version.apple_private_key.id)
  apple_key_secret_version_key   = element(local.apple_key_secret_version_parts, length(local.apple_key_secret_version_parts) - 1)
}

resource "google_cloud_run_service" "digital_membership" {
  provider                   = google-beta
  for_each                   = local.cloud_run_services
  name                       = each.key
  location                   = var.gcp_region
  autogenerate_revision_name = true

  traffic {
    percent         = 100
    latest_revision = true
  }

  metadata {
    annotations = {
      "run.googleapis.com/launch-stage" = "BETA"
    }
  }

  template {

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale"         = "0"
        "autoscaling.knative.dev/maxScale"         = "1"
        "run.googleapis.com/cloudsql-instances"    = google_sql_database_instance.digital_membership.connection_name
        "run.googleapis.com/client-name"           = each.key
        "run.googleapis.com/execution-environment" = "gen2"
        "run.googleapis.com/launch-stage"          = "BETA"
      }
    }

    spec {
      service_account_name = each.value.service_account_name
      containers {
        image = each.value.image

        env {
          name = "DIGITAL_MEMBERSHIP_SECRETS_JSON"
          value_from {
            secret_key_ref {
              name = data.google_secret_manager_secret.digital_membership.secret_id
              key  = local.secret_version_key
            }
          }
        }

        env {
          name  = "DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"
          value = data.google_secret_manager_secret_version.digital_membership.name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_GCP_SQL_CONNECTION_NAME"
          value = google_sql_database_instance.digital_membership.connection_name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME"
          value = google_sql_database_instance.digital_membership.connection_name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_DB_USERNAME"
          value = google_sql_user.service_accounts[each.key].name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"
          value = google_sql_database.database.name
        }
        env {
          name  = "DIGITAL_MEMBERSHIP_BASE_URL"
          value = local.cloud_run_domain_name
        }

        env {
          name  = "GCS_BUCKET_ID"
          value = google_storage_bucket.statics.name
        }

        env {
          name  = "GCLOUD_PROJECT"
          value = var.gcp_project_id
        }

        env {
          name  = "GCLOUD_PUBSUB_TOPIC_ID"
          value = google_pubsub_topic.digital_membership.name
        }

        env {
          name  = "FLASK_ENV"
          value = var.flask_env
        }

        env {
          name  = "LOG_LEVEL"
          value = upper(var.app_log_level)
        }

        env {
          name  = "GOOGLE_PAY_SERVICE_ACCOUNT_EMAIL_ADDRESS"
          value = each.value.service_account_name
        }

        env {
          name  = "GOOGLE_PAY_SERVICE_ACCOUNT_FILE"
          value = "/secrets/service-account-key.json"
        }

        ports {
          name = "http1"
          # protocol       = "TCP"
          container_port = "8080"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "${each.value.memory_mb}Mi"
          }
        }

        dynamic "volume_mounts" {
          for_each = each.value.mount_apple_private_key == true ? [1] : []
          content {
            name       = "apple_developer_private_key"
            mount_path = "/apple-secrets"
          }
        }

        volume_mounts {
          name       = "service_account_key"
          mount_path = "/secrets"
        }

      }

      dynamic "volumes" {
        for_each = each.value.mount_apple_private_key == true ? [1] : []
        content {
          name = "apple_developer_private_key"
          secret {
            secret_name  = data.google_secret_manager_secret.apple_private_key.secret_id
            default_mode = "0444" # 0444
            items {
              key  = local.apple_key_secret_version_key
              path = "private.key"
              # mode = "0444" # 0444
              # mode = 256 # 0400
            }
          }
        }
      }

      volumes {
        name = "service_account_key"
        secret {
          secret_name  = google_secret_manager_secret.service_accounts[each.key].secret_id
          default_mode = "0444" # 0444
          items {
            key  = "latest"
            path = "service-account-key.json"
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
  name     = local.cloud_run_domain_name

  metadata {
    namespace = var.gcp_project_id
  }

  spec {
    route_name = google_cloud_run_service.digital_membership["website"].name
  }
}
