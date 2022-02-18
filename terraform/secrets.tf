resource "random_password" "flask_secret_key" {
  length  = 64
  special = false
}

resource "google_secret_manager_secret" "digital_membership" {
  secret_id = "digital-membership"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret" "service_accounts" {
  for_each = toset([
    "website",
    "worker",
  ])
  secret_id = "${each.key}-service_account_key"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "service_accounts" {
  for_each    = google_secret_manager_secret.service_accounts
  secret      = each.value.id
  secret_data = base64decode(google_service_account_key.digital_membership[each.key].private_key)
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

    recaptcha_secret_key = var.recaptcha_secret_key

    # Flask's secret key: https://flask.palletsprojects.com/en/2.0.x/config/#SECRET_KEY
    secret_key = random_password.flask_secret_key.result

    sendgrid_api_key = var.sendgrid_api_key

    # For configuring python-social-auth / Google OAuth 2 bits:
    social_auth_google_oauth2_key    = var.oauth_client_id
    social_auth_google_oauth2_secret = var.oauth_client_secret

    # Used to for <Squarespace orders> => <AnnualMembership orders> ETL jobs:
    squarespace_api_key       = var.squarespace_api_key
    squarespace_client_id     = var.squarespace_client_id
    squarespace_client_secret = var.squarespace_client_secret
  })
}
