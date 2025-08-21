variable "zone" {
  description = "Exoscale zone"
  type        = string
}

variable "plan" {
  description = "Database plan"
  type        = string
}

variable "pg_version" {
  description = "PostgreSQL version"
  type        = string
}

variable "backup_schedule" {
  description = "Backup schedule (HH:MM format)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "ip_filter" {
  description = "List of CIDR ranges allowed to connect to the DB (e.g., [\"185.19.30.32/32\"])"
  type        = list(string)
  default     = []
}

variable "service_name" {
  description = "Existing DBaaS service name (to avoid replacement)"
  type        = string
}
