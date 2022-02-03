

resource "google_pubsub_topic" "digital_membership" {
  name = "digital-membership"
}

resource "google_pubsub_topic_iam_binding" "digital_membership_topic_publishers" {
  topic = google_pubsub_topic.digital_membership.name
  role  = "roles/pubsub.publisher"
  members = concat(
    [for u in concat(var.gcp_project_owners, var.gcp_project_editors) : "user:${u}"],
    ["serviceAccount:${google_service_account.digital_membership.email}"],
  )
}

locals {
  worker_pubsub_ingress_url = "${google_cloud_run_service.digital_membership["worker"].status[0].url}/pubsub"
}
resource "google_pubsub_subscription" "worker" {
  name  = "worker-subscription"
  topic = google_pubsub_topic.digital_membership.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = local.worker_pubsub_ingress_url
    oidc_token {
      service_account_email = google_service_account.worker_pubsub_invoker.email
    }
    # attributes = {
    #   x-goog-version = "v1"
    # }
  }
}

# resource "google_pubsub_topic_iam_binding" "digital_membership_topic_subscribers" {
#   topic = google_pubsub_topic.digital_membership.name
#   role = "roles/pubsub.subscriber"
#   members = concat(
#     [for u in concat(var.gcp_project_owners, var.gcp_project_editors): "user:${u}"],
#     ["serviceAccount:${google_service_account.digital_membership_worker.email}"],
#   )
# }


# gcloud pubsub subscriptions create myRunSubscription --topic myRunTopic \
#    --push-endpoint=SERVICE-URL/ \
#    --push-auth-service-account=cloud-run-pubsub-invoker@PROJECT_ID.iam.gserviceaccount.com
