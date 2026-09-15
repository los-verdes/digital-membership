# Standing cap on Cloud Logging ingestion volume/cost, independent of the app's
# own LOG_LEVEL setting (see wsgi.py / var.app_log_level). These are project-level
# exclusions, which apply to the "_Default" log sink/bucket -- the one that Cloud
# Logging bills for ingestion+storage -- so entries matching the filter are dropped
# before they're billed, not just before they're routed/stored.
# https://cloud.google.com/logging/docs/exclusions

resource "google_logging_project_exclusion" "cloud_run_below_warning" {
  name        = "cloud-run-below-warning"
  description = "Drop DEBUG/INFO/NOTICE Cloud Run logs (app + request logs) before ingestion, so a misconfigured/reverted LOG_LEVEL can't run up Cloud Logging costs."
  filter      = "resource.type=\"cloud_run_revision\" AND severity<\"WARNING\""
}
