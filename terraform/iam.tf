resource "google_project_iam_member" "project_owners" {
  for_each = toset(var.gcp_project_owners)
  project  = google_project.digital_membership.id
  role     = "roles/owner"
  member   = "user:${each.value}"
}

resource "google_project_iam_member" "project_editors" {
  for_each = toset(var.gcp_project_editors)
  project  = google_project.digital_membership.id
  role     = "roles/editor"
  member   = "user:${each.value}"
}

locals {
  service_account_ids = {
    # TODO: migrate this db-task-runner SA usage to a scheme where we publish a "sync-subscriptions" pubsub message rather than execute it here
    "db-task-runner"        = "Database task runner"
    "website"               = "Digital membership frontend website"
    "worker-pubsub-invoker" = "Digital membership pubsub to worker invoker"
    "worker"                = "Digital membership background worker"
  }
}

resource "time_rotating" "mykey_rotation" {
  rotation_days = 30
}

resource "google_service_account" "digital_membership" {
  for_each     = local.service_account_ids
  account_id   = each.key
  display_name = each.value
}

resource "google_service_account_key" "digital_membership" {
  for_each = toset([
    "website",
    "worker",
  ])
  service_account_id = google_service_account.digital_membership[each.value].name

  keepers = {
    rotation_time = time_rotating.mykey_rotation.rotation_rfc3339
  }
}

resource "google_cloud_run_service_iam_policy" "digital_membership" {
  for_each = google_cloud_run_service.digital_membership
  location = each.value.location
  project  = each.value.project
  service  = each.value.name

  policy_data = data.google_iam_policy.digital_membership[each.key].policy_data
}

data "google_iam_policy" "digital_membership" {
  for_each = local.cloud_run_services
  binding {
    role    = "roles/run.invoker"
    members = each.value.invokers
  }
}

resource "google_secret_manager_secret_iam_policy" "digital_membership" {
  project     = google_secret_manager_secret.digital_membership.project
  secret_id   = google_secret_manager_secret.digital_membership.id
  policy_data = data.google_iam_policy.digital_membership_secret_access.policy_data
}

data "google_iam_policy" "digital_membership_secret_access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.digital_membership["website"].email}",
      "serviceAccount:${google_service_account.digital_membership["db-task-runner"].email}",
      "serviceAccount:${google_service_account.digital_membership["worker"].email}",
    ]
  }
}

resource "google_secret_manager_secret_iam_policy" "service_account_keys" {
  for_each    = google_secret_manager_secret.service_accounts
  project     = each.value.project
  secret_id   = each.value.id
  policy_data = data.google_iam_policy.apple_private_key_secret_access.policy_data
}

resource "google_secret_manager_secret_iam_policy" "apple_private_key" {
  project     = data.google_secret_manager_secret.apple_private_key.project
  secret_id   = data.google_secret_manager_secret.apple_private_key.id
  policy_data = data.google_iam_policy.apple_private_key_secret_access.policy_data
}

data "google_iam_policy" "apple_private_key_secret_access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.digital_membership["website"].email}",
      "serviceAccount:${google_service_account.digital_membership["worker"].email}",
    ]
  }
}

resource "google_project_iam_member" "worker_pubsub_invoker_token_creator" {
  #ts:skip=accurics.gcp.IAM.137 Unable to figure out how this is suppose to work otherwise...
  project = google_project.digital_membership.id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.digital_membership["worker-pubsub-invoker"].email}"
}

# resource "google_project_service_identity" "pubsub" {
#   provider = google-beta

#   project = google_project.digital_membership.project_id
#   service = "pubsub.googleapis.com"
# }

# resource "google_service_account_iam_member" "worker_pubsub_invoker_token_creator" {
#   provider           = google-beta
#   service_account_id = google_project_service_identity.pubsub.id
#   role               = "roles/iam.serviceAccountTokenCreator"
#   member             = "serviceAccount:${google_service_account.digital_membership["worker-pubsub-invoker"].email}"
# }

resource "google_project_iam_binding" "digital_membership_cloudsql_clients" {
  project = google_project.digital_membership.id
  for_each = toset([
    "roles/cloudsql.instanceUser",
    "roles/cloudsql.client",
  ])
  role = each.value
  members = [
    "serviceAccount:${google_service_account.digital_membership["website"].email}",
    "serviceAccount:${google_service_account.digital_membership["worker"].email}",
    "serviceAccount:${google_service_account.digital_membership["db-task-runner"].email}",

  ]
}

resource "google_project_iam_binding" "digital_membership_debugger_agents" {
  project = google_project.digital_membership.id
  role    = "roles/clouddebugger.agent"
  members = [
    "serviceAccount:${google_service_account.digital_membership["website"].email}",
    "serviceAccount:${google_service_account.digital_membership["worker"].email}",
    "serviceAccount:${google_service_account.digital_membership["db-task-runner"].email}",

  ]
}

resource "google_project_iam_binding" "digital_membership_trace_agents" {
  project = google_project.digital_membership.id
  role    = "roles/cloudtrace.agent"
  members = [
    "serviceAccount:${google_service_account.digital_membership["website"].email}",
    "serviceAccount:${google_service_account.digital_membership["worker"].email}",
    "serviceAccount:${google_service_account.digital_membership["db-task-runner"].email}",
  ]
}
# resource "google_project_iam_member" "digital_membership_log_writer" {
#   project = google_project.digital_membership.id
#   role    = "roles/logging.logWriter"
#   member  = "serviceAccount:${google_service_account.digital_membership["website"].email}"
# }

# resource "google_project_iam_member" "db_task_runner_log_writer" {
#   project = google_project.digital_membership.id
#   role    = "roles/logging.logWriter"
#   member  = "serviceAccount:${google_service_account.digital_membership["db-task-runner"].email}"
# }

# resource "google_project_iam_member" "digital_membership_debugger_agent" {
#   project = google_project.digital_membership.id
#   role    = "roles/clouddebugger.agent"
#   member  = "serviceAccount:${google_service_account.digital_membership["website"].email}"
# }

# resource "google_project_iam_member" "digital_membership_trace_agent" {
#   project = google_project.digital_membership.id
#   role    = "roles/cloudtrace.agent"
#   member  = "serviceAccount:${google_service_account.digital_membership["website"].email}"
# }
resource "google_service_account_iam_binding" "allow_sa_impersonation_tokens" {
  service_account_id = google_service_account.digital_membership["website"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  members            = [for u in concat(var.gcp_project_owners, var.gcp_project_editors) : "user:${u}"]
}

resource "google_service_account_iam_binding" "allow_sa_impersonation" {
  service_account_id = google_service_account.digital_membership["website"].name
  role               = "roles/iam.serviceAccountUser"
  members            = [for u in concat(var.gcp_project_owners, var.gcp_project_editors) : "user:${u}"]
}
