project = "digital-membership"

app "digital-membership" {

  build {
    use "docker" {}

    registry {
      use "docker" {
        image = "gcr.io/lv-digital-membership/website"
        tag   = gitrefpretty()
      }
    }
  }

  deploy {
    use "google-cloud-run" {
      project  = "lv-digital-membership"
      location = "us-central1"
      service_account_name = "website@lv-digital-membership.iam.gserviceaccount.com"
      port = 8080

      static_environment = {
        DIGITAL_MEMBERSHIP_GCP_SECRET_NAME = "projects/567739286055/secrets/digital-membership/versions/latest"
        DIGITAL_MEMBERSHIP_SETTINGS_PATH = "member_card.settings.production.ProductionSettings"
      }

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
