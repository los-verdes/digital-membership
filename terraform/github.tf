locals {
  oidc_pool_id = replace(var.github_repo, "/", "-")
}

module "github_oidc" {
  source      = "terraform-google-modules/github-actions-runners/google//modules/gh-oidc"
  version     = "~> 2.0"
  project_id  = var.gcp_project_id
  pool_id     = local.oidc_pool_id
  provider_id = local.oidc_pool_id
  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.sub"              = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.ref"              = "assertion.ref"
    "attribute.environment"      = "assertion.environment"
    "attribute.workflow"         = "assertion.workflow"
    "attribute.job_workflow_ref" = "assertion.job_workflow_ref"
  }
  attribute_condition = "assertion.repository=='${var.github_repo}'"
  sa_mapping = {
    "subcriptions-syncer" = {
      sa_name   = google_service_account.db_task_runner.name
      attribute = "attribute.job_workflow_ref/${var.github_repo}/.github/workflows/sync_subscriptions.yml@refs/heads/main"
    }
    "gh-terraform-applier" = {
      sa_name   = google_service_account.gh_terraform_applier.name
      attribute = "attribute.environment/production"
    }
  }
}

resource "google_service_account" "gh_terraform_applier" {
  account_id   = "gh-terraform-applier"
  display_name = "Identity used for privileged deploys within GitHub Actions workflow runs"
}

resource "google_project_iam_member" "gh_terraform_applier" {
  project = google_project.digital_membership.id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.gh_terraform_applier.email}"
}
