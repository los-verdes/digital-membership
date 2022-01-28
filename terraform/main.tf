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

resource "google_compute_network" "digital_membership" {
  provider = google-beta

  name = "private-network"
}

resource "google_compute_global_address" "digital_membership" {
  provider = google-beta

  name          = "private-ip-address"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.digital_membership.id
}

resource "google_service_networking_connection" "digital_membership" {
  provider = google-beta

  network                 = google_compute_network.digital_membership.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.digital_membership.name]
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

resource "google_service_account" "db_task_runner" {
  account_id   = "db-task-runner"
  display_name = "Database task runner"
}

resource "google_project_iam_member" "digital_membership_datastore_viewer" {
  project = google_project.digital_membership.id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.digital_membership.email}"
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
