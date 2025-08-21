terraform {
  required_providers {
    exoscale = {
      source = "exoscale/exoscale"
    }
  }
}

# Create DBaaS PostgreSQL instance
resource "exoscale_dbaas" "postgres" {
  zone = var.zone
  name = var.service_name
  type = "pg"
  plan = var.plan

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      type,
      name,
      plan,
      # Some providers mark nested settings maps as ForceNew; ignore to avoid churn
      pg,
    ]
  }

  pg {
    version   = var.pg_version
    ip_filter = var.ip_filter
  }
}

# Generate random password for app user
resource "random_password" "app_user_password" {
  length  = 32
  special = true
}
