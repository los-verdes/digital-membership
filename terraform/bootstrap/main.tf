terraform {
  backend "gcs" {
    bucket = "lv-digital-membership-tfstate"
    prefix = "bootstrap"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 3.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 4.8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.4.3"
    }
  }
}

provider "google" {
  project = "lv-digital-membership"
  region  = "us-central1"
}

resource "google_app_engine_application" "digital_membership" {
  project     = google_project.digital_membership.project_id
  location_id = regexall("[-a-z]+", var.gcp_region)[0]
}

# TODO: hook this up with a bot user's oauth creds (not jeffwecan...)
resource "google_sourcerepo_repository" "digital_membership" {
  name = "github_${replace(var.github_repo, "/", "_")}"
}
