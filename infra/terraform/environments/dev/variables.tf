variable "exoscale_api_key" {
  description = "Exoscale API key"
  type        = string
  sensitive   = true
}

variable "exoscale_api_secret" {
  description = "Exoscale API secret"
  type        = string
  sensitive   = true
}

variable "exoscale_zone" {
  description = "Exoscale zone"
  type        = string
  default     = "ch-gva-2"
}

variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "haqnow-community-dev"
}

variable "instance_type" {
  description = "Instance type for the main VM"
  type        = string
  default     = "standard.large"  # 8 vCPU, 16 GB RAM
}

variable "disk_size" {
  description = "Root disk size in GB"
  type        = number
  default     = 200
}

variable "ssh_key" {
  description = "SSH public key for VM access"
  type        = string
}

variable "db_plan" {
  description = "Database plan"
  type        = string
  default     = "startup-4"  # 2 vCPU, 4 GB RAM
}

variable "pg_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15"
}

variable "db_backup_schedule" {
  description = "Database backup schedule"
  type        = string
  default     = "02:00"
}
