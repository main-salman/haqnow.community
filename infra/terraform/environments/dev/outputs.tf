output "instance_public_ip" {
  description = "Public IP address of the main instance"
  value       = module.compute.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the main instance"
  value       = module.compute.private_ip
}

output "database_uri" {
  description = "Database connection URI"
  value       = module.database.uri
  sensitive   = true
}

output "database_host" {
  description = "Database host"
  value       = module.database.host
}

output "database_port" {
  description = "Database port"
  value       = module.database.port
}

output "s3_endpoint" {
  description = "S3-compatible endpoint URL"
  value       = module.storage.endpoint_url
}

output "bucket_names" {
  description = "Created bucket names"
  value       = module.storage.bucket_names
}
