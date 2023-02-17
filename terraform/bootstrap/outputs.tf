output "github_deployer_service_account_email" {
  value = google_service_account.github_deployer.email
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

output "secret_id" {
  value = google_secret_manager_secret_version.digital_membership.id
}
