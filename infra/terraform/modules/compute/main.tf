terraform {
  required_providers {
    exoscale = {
      source = "exoscale/exoscale"
    }
  }
}

# Get Ubuntu 22.04 LTS template
data "exoscale_template" "ubuntu" {
  zone = var.zone
  name = "Linux Ubuntu 22.04 LTS 64-bit"
}

# Create compute instance
resource "exoscale_compute_instance" "main" {
  zone         = var.zone
  name         = "haqnow-community-${var.tags.Environment}"
  template_id  = data.exoscale_template.ubuntu.id
  type         = var.instance_type
  disk_size    = var.disk_size
  ssh_key      = var.ssh_key_name

  security_group_ids = var.security_group_ids

  user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
    docker_compose_version = "2.24.0"
  }))

  labels = var.tags
}

# Create elastic IP
resource "exoscale_elastic_ip" "main" {
  zone        = var.zone
  description = "haqnow-community-${var.tags.Environment}"
  labels      = var.tags
}

# Associate elastic IP with instance (using NIC attachment)
resource "exoscale_nic" "main" {
  compute_id = exoscale_compute_instance.main.id
  network_id = exoscale_elastic_ip.main.id
}
