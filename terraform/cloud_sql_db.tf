resource "random_id" "db_name_suffix" {
  byte_length = 4
}


# TODO: give this fella a private IP only and hook up things eventually
resource "google_sql_database_instance" "digital_membership" {
  name                = "${var.gcp_project_id}-${random_id.db_name_suffix.hex}"
  region              = var.gcp_region
  database_version    = "POSTGRES_13"
  deletion_protection = "true"

  settings {
    tier = "db-f1-micro"
    # disk_size = "2"

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    backup_configuration {
      enabled    = true
      location   = var.gcp_region
      start_time = "07:00"

      backup_retention_settings {
        retained_backups = 1
      }
    }

    ip_configuration {
      ipv4_enabled = true
      require_ssl  = true
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

resource "google_sql_user" "service_accounts" {
  for_each = {
    website        = google_service_account.digital_membership["website"].email,
    db-task-runner = google_service_account.digital_membership["db-task-runner"].email,
    worker         = google_service_account.digital_membership["worker"].email,
  }
  name     = replace(each.value, ".gserviceaccount.com", "")
  instance = google_sql_database_instance.digital_membership.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_sql_user" "users" {
  for_each = toset(concat(var.gcp_project_owners, var.gcp_project_editors))
  name     = lower(each.value)
  instance = google_sql_database_instance.digital_membership.name
  type     = "CLOUD_IAM_USER"
}

# TODO: move SQL roles bootstrap script from bash to a subsequent TF apply w/ postgres provider
# (maybe can wrap the two deals in: https://github.com/mitchellh/terraform-provider-multispace?)
