output "bucket_names" {
  description = "SOS bucket names to be created manually"
  value       = local.bucket_names
}

output "endpoint_url" {
  description = "S3-compatible endpoint URL"
  value       = "https://sos-${var.zone}.exoscale.com"
}
