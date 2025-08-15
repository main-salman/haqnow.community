terraform {
  required_providers {
    exoscale = {
      source  = "exoscale/exoscale"
      version = "~> 0.65"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "exoscale" {
  key    = var.exoscale_api_key
  secret = var.exoscale_api_secret
}

# Get Ubuntu 22.04 LTS template
data "exoscale_template" "ubuntu" {
  zone = var.exoscale_zone
  name = "Linux Ubuntu 22.04 LTS 64-bit"
}

# Create security group
resource "exoscale_security_group" "main" {
  name        = "${var.name_prefix}-sg"
  description = "Security group for Haqnow Community platform"
}

resource "exoscale_security_group_rule" "ssh" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 22
  end_port          = 22
  cidr              = "0.0.0.0/0"
}

resource "exoscale_security_group_rule" "http" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 80
  end_port          = 80
  cidr              = "0.0.0.0/0"
}

resource "exoscale_security_group_rule" "https" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 443
  end_port          = 443
  cidr              = "0.0.0.0/0"
}

resource "exoscale_security_group_rule" "api" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 8000
  end_port          = 8000
  cidr              = "0.0.0.0/0"
}

resource "exoscale_security_group_rule" "frontend" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 3000
  end_port          = 3000
  cidr              = "0.0.0.0/0"
}

# Create compute instance
resource "exoscale_compute_instance" "main" {
  zone         = var.exoscale_zone
  name         = "${var.name_prefix}-server"
  template_id  = data.exoscale_template.ubuntu.id
  type         = var.instance_type
  disk_size    = var.disk_size
  ssh_keys     = [var.ssh_key]

  security_group_ids = [exoscale_security_group.main.id]

  user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
    docker_compose_version = "2.24.0"
  }))
}

# Create elastic IP
resource "exoscale_elastic_ip" "main" {
  zone        = var.exoscale_zone
  description = "${var.name_prefix}-eip"
}

# Create DBaaS PostgreSQL instance (commented out for now)
# resource "exoscale_dbaas" "postgres" {
#   zone = var.exoscale_zone
#   name = "${var.name_prefix}-db"
#   type = "pg"
#   plan = var.db_plan
#
#   pg {
#     version = var.pg_version
#   }
# }

# Generate random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}
