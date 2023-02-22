resource "google_secret_manager_secret" "digital_membership" {
  secret_id = "digital-membership"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "digital_membership" {
  secret      = google_secret_manager_secret.digital_membership.id
  secret_data = var.app_secret_data

  lifecycle {
    # 1. first tf state rm this resource
    # 2. deploy updated version with a tf apply
    # 3. kick off the main deployment pipeline to update the cloud run services to the newly created version
    # 4. (manually) go clean up the version `state rm`'ed in step #1 :)
    prevent_destroy = true
  }
}
