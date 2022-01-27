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



resource "google_project_iam_member" "digital_membership_datastore_viewer" {
  project = google_project.digital_membership.id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.digital_membership.email}"
}
