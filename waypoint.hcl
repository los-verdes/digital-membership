project = "digital-membership"

app "digital-membership" {

  build {
    use "docker" {

    disable_entrypoint = true
    }

    registry {
      use "docker" {
        image = "gcr.io/lv-digital-membership/member-card"
        tag   = gitrefpretty()
      }
    }
  }

  deploy {
    use "google-cloud-run" {
      project  = "lv-digital-membership"
      location = "us-central1"
      service_account_name = "website@lv-digital-membership.iam.gserviceaccount.com"

      static_environment = {
        DIGITAL_MEMBERSHIP_GCP_SECRET_NAME = "projects/567739286055/secrets/digital-membership/versions/latest"
        FLASK_ENV = "production"

        WAYPOINT_CEB_DISABLE = "true"
      }

      cloudsql_instances = ["lv-digital-membership:us-central1:lv-digital-membership"]

      port = 8080
      capacity {
        memory                     = 256
        cpu_count                  = 1
        max_requests_per_container = 10
        request_timeout            = 15
      }

      auto_scaling {
        max = 1
      }
    }
  }

  release {
    use "google-cloud-run" {}
  }

}
