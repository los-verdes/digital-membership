resource "random_password" "flask_secret_key" {
  length  = 64
  special = false
}

# resource "google_secret_manager_secret" "digital_membership" {
#   secret_id = "digital-membership"

#   replication {
#     automatic = true
#   }
# }

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

  lifecycle {
    create_before_destroy = true
  }
}

# We set up this secret outside of Terraform to minimize the possibility of inadvertent leakage...
data "google_secret_manager_secret" "apple_private_key" {
  secret_id = "apple_developer_private_key"
}

data "google_secret_manager_secret_version" "apple_private_key" {
  secret = data.google_secret_manager_secret.apple_private_key.id
}

data "google_secret_manager_secret" "digital_membership" {
  secret_id = "digital-membership"
}


data "google_secret_manager_secret_version" "digital_membership" {
  secret = data.google_secret_manager_secret.digital_membership.id
}
