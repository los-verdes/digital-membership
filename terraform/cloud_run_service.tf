
resource "google_cloud_run_service" "digital_membership" {
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
        "waypoint.hashicorp.com/nonce"          = "2022-01-26T22:43:45.799231Z"
      }
    }

    spec {
      service_account_name = google_service_account.digital_membership.name
      containers {
        image = var.cloud_run_container_image

        env {
          name  = "DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"
          value = google_secret_manager_secret_version.digital_membership.name
        }
        env {
          name  = "FLASK_ENV"
          value = var.flask_env
        }

        # TODO: drop these waypoint bits?
        env {
          name  = "WAYPOINT_CEB_DISABLE"
          value = "true"
        }
        env {
          name  = "WAYPOINT_CEB_INVITE_TOKEN"
          value = "3wADpN5xwNNwfxGZKnk4v9dsDrA7QBxCCxTP7defat9orbjg2HWhG1hUDdDcpDUECn3hcCZ8r8zUukMp7EJKn4xcBZDAVTqyfZ1RZfBL35Mmjd68VCT3pG1uDT9zcZ9UNybEYhwXfZdVg9Q2EA4mhWVy6RMHM1WzgsVrnMzjM2i627jXixvhUhBuTkC6rHh6cMK7KYaBEYBjm4VMR44fkRNF5RjYqD5mfgrKbhQqPmoc7hCZWbuEG"
        }
        env {
          name  = "WAYPOINT_DEPLOYMENT_ID"
          value = "01FTC8XB18A6TPMX2GS6N0RWYY"
        }
        env {
          name  = "WAYPOINT_SERVER_ADDR"
          value = "waypoint-server:9701"
        }
        env {
          name  = "WAYPOINT_SERVER_TLS"
          value = "1"
        }
        env {
          name  = "WAYPOINT_SERVER_TLS_SKIP_VERIFY"
          value = "1"
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
