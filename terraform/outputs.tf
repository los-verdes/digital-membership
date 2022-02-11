locals {
  postgres_connection_url = join(
    "",
    [
      "postgres://",
      google_sql_user.management.name,
      ":",
      random_password.sql_password.result,
      "@",
      google_sql_database_instance.digital_membership.public_ip_address,
      "/",
      google_sql_database.database.name,
    ]
  )
}

output "gh_terraform_applier_service_account_email" {
  value = google_service_account.gh_terraform_applier.email
}

output "github_oidc_provider_name" {
  value = module.github_oidc.provider_name
}

output "postgres_connection_name" {
  value = google_sql_database_instance.digital_membership.connection_name
}

output "postgres_connection_url" {
  value     = local.postgres_connection_url
  sensitive = true
}

output "postgres_public_ip_address" {
  value = google_sql_database_instance.digital_membership.public_ip_address
}

output "postgres_database_name" {
  value = google_sql_database.database.name
}

output "postgres_management_user_name" {
  value = google_sql_user.management.name
}

output "postgres_management_user_password" {
  value     = google_sql_user.management.password
  sensitive = true
}

output "sql_usernames" {
  value = [for u in concat(values(google_sql_user.service_accounts), values(google_sql_user.users)) : u.name]
}

output "project_number" {
  value = google_project.digital_membership.number
}

output "pubsub_topic_id" {
  value = google_pubsub_topic.digital_membership.id
}

output "secret_name" {
  value = google_secret_manager_secret_version.digital_membership.name
}

output "statics_bucket_id" {
  value = google_storage_bucket.statics.id
}

output "website_domain_name" {
  value = local.cloud_run_domain_name
}

output "website_service_account_email" {
  value = google_service_account.digital_membership["website"].email
}

output "worker_pubsub_ingress_url" {
  value = local.worker_pubsub_ingress_url
}

output "worker_service_account_email" {
  value = google_service_account.digital_membership["worker"].email
}

output "worker_pubsub_invoker_service_account_email" {
  value = google_service_account.digital_membership["worker-pubsub-invoker"].email
}
