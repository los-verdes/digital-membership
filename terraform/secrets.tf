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

# We set up this secret outside of Terraform to minimize the possibility of inadvertent leakage...
data "google_secret_manager_secret" "apple_private_key" {
  secret_id = var.apple_pass_private_key_secret_name
}

data "google_secret_manager_secret_version" "apple_private_key" {
  secret = data.google_secret_manager_secret.apple_private_key.id
}

resource "google_secret_manager_secret_version" "digital_membership" {
  secret = google_secret_manager_secret.digital_membership.id
  secret_data = jsonencode({
    # Apple developer cert and private key _password_ (see the `apple_private_key` resource above regarding the key itself)
    apple_pass_certificate          = var.apple_pass_certificate
    apple_pass_private_key_password = var.apple_pass_private_key_password

    # Cloud SQL connection details:
    # db_connection_name = google_sql_database_instance.digital_membership.connection_name
    # db_database_name   = google_sql_database.database.name
    # db_username        = google_sql_user.service_account.name

    recaptcha_secret_key = var.recaptcha_secret_key

    # Flask's secret key: https://flask.palletsprojects.com/en/2.0.x/config/#SECRET_KEY
    secret_key = random_password.flask_secret_key.result

    sendgrid_api_key = var.sendgrid_api_key

    service_account_key = google_service_account_key.digital_membership.private_key

    # For configuring python-social-auth / Google OAuth 2 bits:
    social_auth_google_oauth2_key    = var.oauth_client_id
    social_auth_google_oauth2_secret = var.oauth_client_secret

    # Used to for <Squarespace orders> => <AnnualMembership orders> ETL jobs:
    squarespace_api_key = var.squarespace_api_key
  })
}

resource "google_secret_manager_secret_iam_policy" "digital_membership" {
  project     = google_secret_manager_secret.digital_membership.project
  secret_id   = google_secret_manager_secret.digital_membership.id
  policy_data = data.google_iam_policy.digital_membership_secret_access.policy_data
}

data "google_iam_policy" "digital_membership_secret_access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.digital_membership.email}",
      "serviceAccount:${google_service_account.db_task_runner.email}",
      "serviceAccount:${google_service_account.digital_membership_worker.email}",
    ]
  }
}

resource "google_secret_manager_secret_iam_policy" "apple_private_key" {
  project     = data.google_secret_manager_secret.apple_private_key.project
  secret_id   = data.google_secret_manager_secret.apple_private_key.id
  policy_data = data.google_iam_policy.apple_private_key_secret_access.policy_data
}

data "google_iam_policy" "apple_private_key_secret_access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.digital_membership.email}",
      "serviceAccount:${google_service_account.digital_membership_worker.email}",
    ]
  }
}
# resource "google_project_iam_member" "digital_membership_datastore_viewer" {
#   project = google_project.digital_membership.id
#   role    = "roles/datastore.viewer"
#   member  = "serviceAccount:${google_service_account.digital_membership.email}"
# }
