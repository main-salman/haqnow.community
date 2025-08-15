output "uri" {
  description = "Database connection URI"
  value       = exoscale_database.postgres.uri
  sensitive   = true
}

output "host" {
  description = "Database host"
  value       = exoscale_database.postgres.host
}

output "port" {
  description = "Database port"
  value       = exoscale_database.postgres.port
}

output "username" {
  description = "App user username"
  value       = exoscale_database_user.app_user.username
}

output "password" {
  description = "App user password"
  value       = exoscale_database_user.app_user.password
  sensitive   = true
}
