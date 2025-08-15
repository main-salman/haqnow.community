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
}

# Generate random password for app user
resource "random_password" "app_user_password" {
  length  = 32
  special = true
}
