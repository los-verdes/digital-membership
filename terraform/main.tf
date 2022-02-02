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

resource "google_service_account" "digital_membership" {
  account_id   = "website"
  display_name = "website"
}

resource "time_rotating" "digital_membership_key_rotation" {
  rotation_days = 30
}

resource "google_service_account_key" "digital_membership" {
  service_account_id = google_service_account.digital_membership.name

  keepers = {
    rotation_time = time_rotating.digital_membership_key_rotation.rotation_rfc3339
  }
}

resource "google_service_account" "db_task_runner" {
  account_id   = "db-task-runner"
  display_name = "Database task runner"
}

resource "google_project_iam_member" "digital_membership_cloudsql_client" {
  project = google_project.digital_membership.id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.digital_membership.email}"
}

resource "google_project_iam_member" "db_task_runner_cloudsql_client" {
  project = google_project.digital_membership.id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.db_task_runner.email}"
}

resource "google_project_iam_member" "digital_membership_log_writer" {
  project = google_project.digital_membership.id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.digital_membership.email}"
}

resource "google_project_iam_member" "db_task_runner_log_writer" {
  project = google_project.digital_membership.id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.db_task_runner.email}"
}

resource "google_project_iam_member" "digital_membership_debugger_agent" {
  project = google_project.digital_membership.id
  role    = "roles/clouddebugger.agent"
  member  = "serviceAccount:${google_service_account.digital_membership.email}"
}

resource "google_project_iam_member" "digital_membership_trace_agent" {
  project = google_project.digital_membership.id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.digital_membership.email}"
}

# TODO: hook this up with a bot user's oauth creds (not jeffwecan...)
resource "google_sourcerepo_repository" "digital_membership" {
  name = "github_${replace(var.github_repo, "/", "_")}"
}

resource "google_service_account_iam_binding" "allow_sa_impersonation_tokens" {
  service_account_id = google_service_account.digital_membership.name
  role               = "roles/iam.serviceAccountTokenCreator"
  members            = [for u in concat(var.gcp_project_owners, var.gcp_project_editors) : "user:${u}"]
}

resource "google_service_account_iam_binding" "allow_sa_impersonation" {
  service_account_id = google_service_account.digital_membership.name
  role               = "roles/iam.serviceAccountUser"
  members            = [for u in concat(var.gcp_project_owners, var.gcp_project_editors) : "user:${u}"]
}
