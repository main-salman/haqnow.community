# Haqnow Community Infrastructure

Terraform configuration for deploying Haqnow Community on Exoscale.

## Prerequisites

1. Install Terraform >= 1.0
2. Get Exoscale API credentials from the console
3. Create an SSH key pair for VM access

## Setup

1. Copy the example variables file:
   ```bash
   cd environments/dev
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` with your Exoscale credentials and preferences

3. Initialize Terraform:
   ```bash
   terraform init
   ```

4. Plan the deployment:
   ```bash
   terraform plan
   ```

5. Apply the configuration:
   ```bash
   terraform apply
   ```

## What gets created

- **Compute**: Ubuntu 22.04 VM with Docker and Docker Compose pre-installed
- **Security**: Security group allowing SSH (22), HTTP (80), and HTTPS (443)
- **Database**: PostgreSQL 15 DBaaS instance with app user
- **Storage**: 5 SOS buckets for different file types
- **Network**: Elastic IP for the VM

## After deployment

1. Get the VM IP address:
   ```bash
   terraform output instance_public_ip
   ```

2. Update your `.env` file with the outputs:
   ```bash
   # Add to .env
   SERVER_IP=$(terraform output -raw instance_public_ip)
   DATABASE_URL=$(terraform output -raw database_uri)
   S3_ENDPOINT=$(terraform output -raw s3_endpoint)
   ```

3. SSH to the VM and deploy the application:
   ```bash
   ssh ubuntu@$(terraform output -raw instance_public_ip)
   ```

## Cleanup

To destroy all resources:
```bash
terraform destroy
```
