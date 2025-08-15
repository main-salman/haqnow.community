output "instance_ip_address" {
  description = "The public IP address of the main compute instance"
  value       = exoscale_compute_instance.main.public_ip_address
}

# Elastic IP removed - using direct instance IP

output "db_info" {
  description = "PostgreSQL database information"
  value       = "Database will be available after deployment. Check Exoscale console for connection details."
}

output "s3_endpoint" {
  description = "Exoscale S3 endpoint URL"
  value       = "https://sos-${var.exoscale_zone}.exoscale.com"
}

output "bucket_names_to_create" {
  description = "S3 bucket names that need to be created manually"
  value = [
    "${var.name_prefix}-originals",
    "${var.name_prefix}-normalized",
    "${var.name_prefix}-derivatives",
    "${var.name_prefix}-exports",
    "${var.name_prefix}-trash"
  ]
}

output "deployment_instructions" {
  description = "Next steps for deployment"
  value = <<-EOT
    1. SSH to server: ssh ubuntu@${exoscale_compute_instance.main.public_ip_address}
    2. Clone repository and deploy with Docker Compose
    3. Create S3 buckets manually in Exoscale console
    4. Configure DNS to point to: ${exoscale_compute_instance.main.public_ip_address}
    5. Set up SSL certificates with Let's Encrypt
  EOT
}
