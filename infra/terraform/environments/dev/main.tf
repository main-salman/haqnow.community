terraform {
  required_providers {
    exoscale = {
      source  = "exoscale/exoscale"
      version = "~> 0.59"
    }
  }
  required_version = ">= 1.0"
}

provider "exoscale" {
  key    = var.exoscale_api_key
  secret = var.exoscale_api_secret
}

# Use modules for reusable components
module "compute" {
  source = "../../modules/compute"
  
  zone                = var.zone
  instance_type       = var.instance_type
  disk_size          = var.disk_size
  ssh_key_name       = var.ssh_key_name
  security_group_ids = [module.security.security_group_id]
  
  tags = {
    Environment = "dev"
    Project     = "haqnow-community"
  }
}

module "security" {
  source = "../../modules/security"
  
  zone = var.zone
  
  tags = {
    Environment = "dev"
    Project     = "haqnow-community"
  }
}

module "database" {
  source = "../../modules/database"
  
  zone            = var.zone
  plan            = var.db_plan
  pg_version      = var.pg_version
  backup_schedule = var.db_backup_schedule
  
  tags = {
    Environment = "dev"
    Project     = "haqnow-community"
  }
}

module "storage" {
  source = "../../modules/storage"
  
  zone = var.zone
  
  buckets = [
    "haqnow-dev-originals",
    "haqnow-dev-tiles",
    "haqnow-dev-ocr",
    "haqnow-dev-thumbnails",
    "haqnow-dev-exports"
  ]
  
  tags = {
    Environment = "dev"
    Project     = "haqnow-community"
  }
}
