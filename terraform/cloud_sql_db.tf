# TODO: give this fella a private IP only and hook up things eventually
resource "google_sql_database_instance" "digital_membership" {
  name                = var.gcp_project_id
  region              = var.gcp_region
  database_version    = "POSTGRES_13"
  deletion_protection = "true"

  settings {
    tier = "db-f1-micro"
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    backup_configuration {
      enabled    = true
      location   = var.gcp_region
      start_time = "07:00"

      backup_retention_settings {
        retained_backups = 3
      }

    }
  }
}

resource "google_sql_database" "database" {
  name     = var.gcp_project_id
  instance = google_sql_database_instance.digital_membership.name
}

resource "google_sql_user" "mangement" {
  name     = "tf-management"
  password = random_password.sql_password.result
  instance = google_sql_database_instance.digital_membership.name
  type     = "BUILT_IN"
}

resource "google_sql_user" "service_account" {
  name     = replace(google_service_account.digital_membership.email, ".gserviceaccount.com", "")
  instance = google_sql_database_instance.digital_membership.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_sql_user" "users" {
  for_each = toset(concat(var.gcp_project_owners, var.gcp_project_editors))
  name     = each.value
  instance = google_sql_database_instance.digital_membership.name
  type     = "CLOUD_IAM_USER"
}