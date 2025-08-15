variable "zone" {
  description = "Exoscale zone"
  type        = string
}

variable "instance_type" {
  description = "Instance type"
  type        = string
}

variable "disk_size" {
  description = "Root disk size in GB"
  type        = number
}

variable "ssh_key_name" {
  description = "SSH key name"
  type        = string
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
