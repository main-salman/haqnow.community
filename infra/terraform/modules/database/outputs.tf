output "service_name" {
  description = "DBaaS service name"
  value       = exoscale_dbaas.postgres.name
}

// App user outputs removed (not managed here)
