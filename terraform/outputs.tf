output "gh_terraform_applier_sa_email" {
  value = google_service_account.gh_terraform_applier.email
}

output "github_oidc_provider_name" {
  value = module.github_oidc.provider_name
}

output "project_number" {
  value = google_project.digital_membership.number
}

output "secret_name" {
  value = google_secret_manager_secret_version.digital_membership.name
}

output "website_sa_email" {
  value = google_service_account.digital_membership.email
}


locals {
  postgres_connection_url = join(
    "",
    [
      "postgres://",
      google_sql_user.users.name,
      ":",
      random_password.sql_password.result,
      "@",
      google_sql_database_instance.digital_membership.public_ip_address,
      "/",
      google_sql_database.database.name,
    ]
  )
}

output "postgres_connection_url" {
  value     = local.postgres_connection_url
  sensitive = true
}
