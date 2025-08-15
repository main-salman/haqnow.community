terraform {
  required_providers {
    exoscale = {
      source = "exoscale/exoscale"
    }
  }
}

# Create DBaaS PostgreSQL instance
resource "exoscale_database" "postgres" {
  zone = var.zone
  name = "haqnow-community-${var.tags.Environment}"
  type = "pg"
  plan = var.plan
  
  pg_settings = {
    version = var.pg_version
  }
  
  backup_schedule = var.backup_schedule
  
  labels = var.tags
}

# Create database user
resource "exoscale_database_user" "app_user" {
  zone     = var.zone
  database = exoscale_database.postgres.id
  username = "haqnow_app"
  password = random_password.app_user_password.result
}

# Generate random password for app user
resource "random_password" "app_user_password" {
  length  = 32
  special = true
}
