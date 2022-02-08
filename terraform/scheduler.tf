resource "google_cloud_scheduler_job" "sync_subscriptions_etl" {
  name        = "sync-subscriptions-etl"
  description = "Regularly recurring Squarespace order into membership database ETL task"
  schedule    = "0 */6 * * *"

  pubsub_target {
    topic_name = google_pubsub_topic.digital_membership.id
    data = base64encode(jsonencode({
      type = "sync_subscriptions_etl",
    }))
  }
}
