resource "random_password" "flask_secret_key" {
  length  = 64
  special = false
}

resource "random_password" "sql_password" {
  length  = 64
  special = false
}


resource "google_secret_manager_secret" "digital_membership" {
  secret_id = "digital-membership"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "digital_membership" {
  secret = google_secret_manager_secret.digital_membership.id
  secret_data = jsonencode({
    apple_pass_certificate          = var.apple_pass_certificate
    apple_pass_private_key          = var.apple_pass_private_key
    apple_pass_private_key_password = var.apple_pass_private_key_password
    sql_database_name               = google_sql_database.database.name
    sql_connection_name             = google_sql_database_instance.digital_membership.connection_name
    sql_username                    = google_sql_user.service_account.name
    # sql_password                    = random_password.sql_password.result
    flask_secret_key    = random_password.flask_secret_key.result
    squarespace_api_key = var.squarespace_api_key
    oauth_client_id     = var.oauth_client_id
    oauth_client_secret = var.oauth_client_secret
  })
}

resource "google_secret_manager_secret_iam_policy" "digital_membership" {
  project     = google_secret_manager_secret.digital_membership.project
  secret_id   = google_secret_manager_secret.digital_membership.id
  policy_data = data.google_iam_policy.secrets_access.policy_data
}

data "google_iam_policy" "secrets_access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      # "serviceAccount:567739286055-compute@developer.gserviceaccount.com",
      "serviceAccount:${google_service_account.digital_membership.email}",
    ]
  }
}


# resource "google_project_iam_member" "digital_membership_datastore_viewer" {
#   project = google_project.digital_membership.id
#   role    = "roles/datastore.viewer"
#   member  = "serviceAccount:${google_service_account.digital_membership.email}"
# }
