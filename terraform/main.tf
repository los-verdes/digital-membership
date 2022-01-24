terraform {
  backend "gcs" {
    bucket = "lv-digital-membership-tfstate"
    prefix = "env/production"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "google_app_engine_application" "digital_membership" {
  project       = google_project.digital_membership.project_id
  location_id   = regexall("[-a-z]+", var.gcp_region)[0]
  database_type = "CLOUD_FIRESTORE"
}

# resource "google_cloud_run_service" "digital_membership" {
#   name     = "digital-membership"
#   location = var.gcp_region

#   template {
#     spec {
#       containers {
#         image = "gcr.io/lv-digital-membership/member-card"
#       }
#     }

#     metadata {
#       annotations = {
#         "autoscaling.knative.dev/maxScale"      = "1"
#         "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.digital_membership.connection_name
#         "run.googleapis.com/client-name"        = "member-card"
#       }
#     }
#   }
#   autogenerate_revision_name = true
# }
# import 'google_cloud_run_service.digital_membership' 'us-central1/digital-membership'
resource "google_sql_database_instance" "digital_membership" {
  name             = var.gcp_project_id
  region           = var.gcp_region
  database_version = "POSTGRES_13"
  settings {
    tier = "db-f1-micro"
  }

  deletion_protection = "true"
}

resource "google_sql_database" "database" {
  name     = var.gcp_project_id
  instance = google_sql_database_instance.digital_membership.name
}


# output "postgres_connection" {
#   value = google_sql_database_instance.digital_membership
# }
output "postgres_connection_name" {
  value = google_sql_database_instance.digital_membership.connection_name
}
resource "google_sql_user" "users" {
  name     = replace(google_service_account.digital_membership.email, ".gserviceaccount.com", "")
  password = random_password.sql_password.result
  instance = google_sql_database_instance.digital_membership.name
  type     = "BUILT_IN"
}

# resource "google_sql_user" "me" {
#   name     = "jeff.hogan1@gmail.com"
#   password = random_password.sql_password.result
#   instance = google_sql_database_instance.digital_membership.name
#   type     = "BUILT_IN"
# }


# resource "google_sql_user" "users" {
#   name     = google_service_account.digital_membership.email
#   instance = google_sql_database_instance.master.name
#   type     = "CLOUD_IAM_USER"
# }
