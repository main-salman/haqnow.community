variable "zone" {
  description = "Exoscale zone"
  type        = string
}

variable "buckets" {
  description = "List of bucket names to create"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
