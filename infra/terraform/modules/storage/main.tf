terraform {
  required_providers {
    exoscale = {
      source = "exoscale/exoscale"
    }
  }
}

# Note: SOS buckets need to be created manually or via API
# The Terraform provider doesn't currently support SOS bucket creation
# For now, we'll output the bucket names that need to be created manually

locals {
  bucket_names = [
    "${var.name_prefix}-originals",
    "${var.name_prefix}-normalized",
    "${var.name_prefix}-derivatives",
    "${var.name_prefix}-exports",
    "${var.name_prefix}-trash"
  ]
}
