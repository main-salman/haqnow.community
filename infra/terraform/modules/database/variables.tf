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
