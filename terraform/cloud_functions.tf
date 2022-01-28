# data "google_storage_bucket" "cloud_functions" {
#   name = "lv-digital-membership-tfstate"
#   # name = "gcf-sources-${google_project.digital_membership.number}-${var.gcp_region}"
# }

# data "archive_file" "sync_subscriptions_function" {
#   type             = "zip"
#   output_file_mode = "0666"
#   output_path      = "${path.module}/sync_subscriptions_function.zip"
#   source_dir       = "${path.module}/.."
#   excludes = tolist(
#     setunion(
#       fileset("${path.module}/../.github", "**"),
#       fileset("${path.module}/../postgres-data", "**"),
#       fileset("${path.module}/../scripts", "**"),
#       fileset(path.module, "**"),
#     )
#   )
# }

# resource "google_storage_bucket_object" "sync_subscriptions_archive" {
#   name   = "archive/functions/sync_subscriptions_${data.archive_file.sync_subscriptions_function.output_sha}.zip"
#   bucket = data.google_storage_bucket.cloud_functions.name
#   source = data.archive_file.sync_subscriptions_function.output_path
# }

# # resource "google_service_account" "sync_subscriptions_function" {
# #   account_id   = "sync_subscriptions"
# #   display_name = var.page_description
# # }

# resource "google_cloudfunctions_function" "sync_subscriptions" {
#   name        = "sync-subscriptions"
#   description = "Listens for calendar-event-related drive changes"
#   runtime     = "python39"

#   available_memory_mb = 256
#   max_instances       = 1
#   timeout             = 540 # setting to the max (9 minutes)
#   # service_account_email = google_service_account.sync_subscriptions_function.email
#   service_account_email = google_service_account.digital_membership.email
#   source_archive_bucket = data.google_storage_bucket.cloud_functions.name
#   source_archive_object = google_storage_bucket_object.sync_subscriptions_archive.name
#   trigger_http          = false
#   entry_point           = "sync_subscriptions"
#   event_trigger {
#     event_type
#     resource
#   }

#   environment_variables = {
#     FLASK_ENV                          = "cloudfunction"
#     DIGITAL_MEMBERSHIP_GCP_SECRET_NAME = google_secret_manager_secret_version.digital_membership.name
#     DIGITAL_MEMBERSHIP_SKU             = var.membership_squarespace_sku
#   }

#   build_environment_variables = {
#     GOOGLE_FUNCTION_SOURCE = "cloudfunction.py"
#   }
# }

# # TODO: can we narrow this down to just GCP/Google authenticated robots?
# resource "google_cloudfunctions_function_iam_member" "sync_subscriptions_allow_invocations" {
#   project        = google_cloudfunctions_function.sync_subscriptions.project
#   region         = google_cloudfunctions_function.sync_subscriptions.region
#   cloud_function = google_cloudfunctions_function.sync_subscriptions.name

#   role   = "roles/cloudfunctions.invoker"
#   member = "projectOwner:${google_project.digital_membership.name}"
# }
