output "instance_id" {
  description = "Instance ID"
  value       = exoscale_compute_instance.main.id
}

output "public_ip" {
  description = "Public IP address"
  value       = exoscale_elastic_ip.main.ip_address
}

output "private_ip" {
  description = "Private IP address"
  value       = exoscale_compute_instance.main.private_network_ip_address
}
