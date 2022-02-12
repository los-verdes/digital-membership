terraform {
  backend "gcs" {
    bucket = "lv-digital-membership-tfstate"
    prefix = "env/production-database"
  }

  required_providers {
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.15.0"
    }
  }
}

data "terraform_remote_state" "production" {
  backend = "gcs"

  config = {
    bucket = "lv-digital-membership-tfstate"
    prefix = "env/production"
  }
}

locals {
  database_host = data.terraform_remote_state.production.outputs.postgres_connection_name
  database_name = data.terraform_remote_state.production.outputs.postgres_database_name

  management_user_name     = data.terraform_remote_state.production.outputs.postgres_management_user_name
  management_user_password = data.terraform_remote_state.production.outputs.postgres_management_user_password

  sql_users = concat(
    [data.terraform_remote_state.production.outputs.postgres_management_user_name],
    data.terraform_remote_state.production.outputs.sql_usernames,
  )
}

provider "postgresql" {
  # scheme          = "gcppostgres"
  host            = "127.0.0.1"
  port            = 5432
  database        = local.database_name
  username        = local.management_user_name
  password        = local.management_user_password
  sslmode         = "disable"
  connect_timeout = 15
}

resource "postgresql_role" "read_write" {
  name  = "read_write"
  roles = []
}

resource "postgresql_grant_role" "read_write" {
  for_each   = toset(local.sql_users)
  role       = each.value
  grant_role = "read_write"
}

resource "postgresql_grant" "read_write_connect" {
  role        = postgresql_role.read_write.name
  database    = local.database_name
  object_type = "database"
  privileges  = ["CONNECT"]
}

resource "postgresql_grant" "read_write_usage_schema" {
  role        = postgresql_role.read_write.name
  database    = local.database_name
  schema      = "public"
  object_type = "schema"
  privileges  = ["USAGE", "CREATE"]
}

resource "postgresql_grant" "read_write_usage_seqs" {
  role        = postgresql_role.read_write.name
  database    = local.database_name
  schema      = "public"
  object_type = "sequence"
  privileges  = ["USAGE"]
}

resource "postgresql_grant" "read_write_crud_public" {
  role        = postgresql_role.read_write.name
  database    = local.database_name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]
}

resource "postgresql_default_privileges" "read_write_tables" {
  role     = postgresql_role.read_write.name
  database = local.database_name
  schema   = "public"

  owner       = local.management_user_name
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]
}

resource "postgresql_default_privileges" "read_write_usage_seqs" {
  role     = postgresql_role.read_write.name
  database = local.database_name
  schema   = "public"

  owner       = local.management_user_name
  object_type = "sequence"
  privileges  = ["USAGE"]
}

# resource "postgresql_role" "read_only" {
#   name  = "read_only"
#   roles = []
# }

# resource "postgresql_grant" "read_only_connect" {
#   role        = postgresql_role.read_only.name
#   database    = local.database_name
#   object_type = "database"
#   privileges  = ["CONNECT"]
# }

# resource "postgresql_grant" "read_only_usage" {
#   role        = postgresql_role.read_only.name
#   database    = local.database_name
#   schema      = "public"
#   object_type = "schema"
#   privileges  = ["USAGE"]
# }

# resource "postgresql_grant" "read_only_select_all_public" {
#   role        = postgresql_role.read_only.name
#   database    = local.database_name
#   schema      = "public"
#   object_type = "table"
#   privileges  = ["SELECT"]
# }

# resource "postgresql_default_privileges" "read_only_tables" {
#   role     = postgresql_role.read_only.name
#   database = local.database_name
#   schema   = "public"

#   owner       = postgresql_role.read_only.name
#   object_type = "table"
#   privileges  = ["SELECT"]
# }
