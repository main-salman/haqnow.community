output "bucket_names" {
  description = "Created bucket names"
  value       = [for bucket in exoscale_sos_bucket.buckets : bucket.name]
}

output "endpoint_url" {
  description = "S3-compatible endpoint URL"
  value       = "https://sos-${var.zone}.exo.io"
}
