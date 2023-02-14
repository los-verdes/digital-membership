resource "google_secret_manager_secret" "digital_membership" {
  secret_id = "digital-membership"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "digital_membership" {
  secret      = google_secret_manager_secret.digital_membership.id
  secret_data = var.app_secret_data
}
