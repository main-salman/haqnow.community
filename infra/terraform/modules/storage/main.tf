terraform {
  required_providers {
    exoscale = {
      source = "exoscale/exoscale"
    }
  }
}

# Create SOS buckets
resource "exoscale_sos_bucket" "buckets" {
  for_each = toset(var.buckets)
  
  zone = var.zone
  name = each.value
  
  labels = var.tags
}
