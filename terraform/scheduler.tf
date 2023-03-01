locals {
  scheduler_jobs = {
    run_slack_members_etl = {
      description = "Sync Slack member / user data into local digital membership database"
      schedule    = "0 */6 * * *"
      data = {
        type = "run_slack_members_etl",
      }
    }
  }
}

resource "google_cloud_scheduler_job" "worker" {
  for_each    = local.scheduler_jobs
  name        = each.key
  description = each.value.description
  schedule    = each.value.schedule

  pubsub_target {
    topic_name = google_pubsub_topic.digital_membership.id
    data       = base64encode(jsonencode(each.value.data))
  }
}

resource "google_cloud_scheduler_job" "sync_subscriptions_etl" {
  name        = "sync-subscriptions-etl"
  description = "Regularly recurring Squarespace order into membership database ETL task"
  schedule    = "0 * * * *"

  pubsub_target {
    topic_name = google_pubsub_topic.digital_membership.id
    data = base64encode(jsonencode({
      type = "sync_subscriptions_etl",
    }))
  }
}
