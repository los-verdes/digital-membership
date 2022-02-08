resource "google_project" "digital_membership" {
  name            = var.gcp_project_name
  project_id      = var.gcp_project_id
  billing_account = var.gcp_billing_account_id

  auto_create_network = false
}

resource "google_project_service" "digital_membership" {
  for_each = toset([
    # For gh-oidc module
    # Reference: https://github.com/terraform-google-modules/terraform-google-github-actions-runners/tree/master/modules/gh-oidc#requirements
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iamcredentials.googleapis.com", # IAM Credentials API
    "sts.googleapis.com",

    # Seemingly required for service-account-based applies of this config to avoid this here error:
    # ... Error when reading or editing Project Service lv-digital-membership/iam.googleapis.com: ...
    "serviceusage.googleapis.com",

    # For our "memberships" "database": TODO: clean this up at some point...
    # "firestore.googleapis.com",

    "secretmanager.googleapis.com", # direct usage

    "containerregistry.googleapis.com", # hosting cloudrun images
    "run.googleapis.com",

    # "bigquery.googleapis.com",
    "sqladmin.googleapis.com", # for connecting to sql from cloudrun?

    "compute.googleapis.com", # Needed to edit Cloud SQL config via the console for some reason?

    # APM and debugging thingers:
    "clouddebugger.googleapis.com",
    "cloudtrace.googleapis.com",

    # Building thangs:
    "sourcerepo.googleapis.com",
    "cloudbuild.googleapis.com",

    # For our sync subscriptions cloud function:
    # "cloudfunctions.googleapis.com",

    # private IP jazz for cloud sql:
    # "servicenetworking.googleapis.com",

    # Google Pay Passes API
    "walletobjects.googleapis.com",

    # For TF applies by a service account(?):
    # │ Error: Error when reading or editing App Engine Application "lv-digital-membership":
    # googleapi: Error 403: App Engine Admin API has not been used in project ...
    "appengine.googleapis.com",

    # Email distribution requests / background worker tasks generally
    "pubsub.googleapis.com",

    # For scheduled ETL tasks and such
    "cloudscheduler.googleapis.com",
  ])

  service                    = each.value
  disable_dependent_services = true

  timeouts {
    create = "30m"
    update = "40m"
  }
}
