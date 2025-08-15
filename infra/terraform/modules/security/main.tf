terraform {
  required_providers {
    exoscale = {
      source = "exoscale/exoscale"
    }
  }
}

# Create security group
resource "exoscale_security_group" "main" {
  name        = "haqnow-community-${var.tags.Environment}"
  description = "Security group for Haqnow Community ${var.tags.Environment}"
}

# SSH access
resource "exoscale_security_group_rule" "ssh" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 22
  end_port          = 22
  cidr              = "0.0.0.0/0"
  description       = "SSH access"
}

# HTTP access
resource "exoscale_security_group_rule" "http" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 80
  end_port          = 80
  cidr              = "0.0.0.0/0"
  description       = "HTTP access"
}

# HTTPS access
resource "exoscale_security_group_rule" "https" {
  security_group_id = exoscale_security_group.main.id
  type              = "INGRESS"
  protocol          = "TCP"
  start_port        = 443
  end_port          = 443
  cidr              = "0.0.0.0/0"
  description       = "HTTPS access"
}

# Allow all outbound traffic
resource "exoscale_security_group_rule" "egress" {
  security_group_id = exoscale_security_group.main.id
  type              = "EGRESS"
  protocol          = "TCP"
  start_port        = 1
  end_port          = 65535
  cidr              = "0.0.0.0/0"
  description       = "All outbound traffic"
}
