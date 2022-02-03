resource "google_storage_bucket" "statics" {
  name          = "cstatic.${var.base_domain}"
  location      = "US"
  force_destroy = true

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
  }
}

resource "google_storage_bucket_iam_member" "all_users_viewers" {
  bucket = google_storage_bucket.statics.name
  role   = "roles/storage.legacyObjectReader"
  member = "allUsers"
}

resource "google_storage_bucket_iam_member" "digital_membership_sa_obj_admin" {
  bucket = google_storage_bucket.statics.name
  role   = "roles/storage.legacyObjectOwner"
  member = "serviceAccount:${google_service_account.digital_membership.email}"
}


resource "google_storage_bucket_iam_member" "digital_membership_sa_bucket_reader" {
  bucket = google_storage_bucket.statics.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.digital_membership.email}"
}


resource "google_storage_bucket_iam_member" "digital_membership_worker_sa_obj_admin" {
  bucket = google_storage_bucket.statics.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.digital_membership_worker.email}"
}


resource "google_storage_bucket_iam_member" "digital_membership_worker_sa_obj_owner" {
  bucket = google_storage_bucket.statics.name
  role   = "roles/storage.legacyObjectOwner"
  member = "serviceAccount:${google_service_account.digital_membership_worker.email}"
}


resource "google_storage_bucket_iam_member" "digital_membership_worker_sa_bucket_reader" {
  bucket = google_storage_bucket.statics.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.digital_membership_worker.email}"
}


# resource "google_storage_bucket_iam_member" "test_site_publisher_sa_obj_admin" {
#   bucket = google_storage_bucket.static_site.name
#   role   = "roles/storage.objectAdmin"
#   member = "serviceAccount:${google_service_account.test_site_publisher.email}"w

#   # condition {
#   #   title       = "tests-prefix-only"
#   #   description = "Only allow object admin under a tests/ prefix"
#   #   expression  = <<-expression
#   #     resource.name.startsWith(“projects/_/buckets/${google_storage_bucket.static_site.name}/objects/tests”)
#   #     expression
#   # }
# }

# data "cloudflare_zone" "static_site" {
#   name = var.cloudflare_zone
# }

# resource "cloudflare_record" "static_site" {
#   zone_id = data.cloudflare_zone.static_site.id
#   name    = var.static_site_hostname
#   value   = "c.storage.googleapis.com"
#   type    = "CNAME"
#   ttl     = 1
#   proxied = true
# }
