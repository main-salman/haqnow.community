# Haqnow Community Platform - Deployment Guide

## 🚀 **PLATFORM STATUS: READY FOR DEPLOYMENT**

The Haqnow Community platform is now **fully implemented** and ready for production deployment on Exoscale. This guide will walk you through the complete deployment process.

## 📋 **What's Been Built**

### ✅ **Core Infrastructure (M1)**
- **Terraform Configuration**: Complete infrastructure as code for Exoscale
- **Docker Compose**: Multi-service stack (API, Worker, Redis, Frontend)
- **Cloud-init**: Automated server setup with Docker, Nginx, and deployment scripts
- **Security Groups**: Properly configured firewall rules

### ✅ **Authentication & Admin (M2)**
- **User Management**: Create users with TOTP MFA, role-based access control
- **API Key Management**: Issue, list, and revoke API keys with scopes
- **Authentication Flow**: Login with password + TOTP verification, JWT tokens
- **Admin Console**: Complete UI for user and API key management

### ✅ **Document Processing (M3)**
- **Document Registry**: Upload, list, retrieve documents with metadata
- **Processing Pipeline**: Automatic background jobs for tiling, thumbnails, OCR
- **Real Processing Logic**:
  - PDF/image rasterization at 300 DPI using PyMuPDF
  - WebP tile generation (256x256) for efficient viewing
  - Thumbnail generation for UI previews
  - OCR text extraction with Tesseract
- **S3 Integration**: Presigned upload endpoints for direct file uploads

### ✅ **Search & UI (M4)**
- **Search API**: Full-text search with faceted filtering
- **Modern Frontend**: React + TypeScript with Tailwind CSS
- **Document Management**: Complete CRUD interface with filtering
- **Dashboard**: Overview with statistics and recent activity

### ✅ **Document Viewer (M5)**
- **Tiled Image Viewer**: OpenSeadragon-based viewer with pan/zoom
- **Navigation Controls**: Zoom, rotate, fullscreen, page navigation
- **Sidebar Interface**: Document info, comments, AI Q&A tabs
- **Processing Status**: Real-time job progress tracking

### ✅ **Admin Interface (M7)**
- **User Management UI**: Create users, assign roles, manage status
- **API Key Management UI**: Generate keys, set scopes, revoke access
- **Modern Design**: Apple-inspired, responsive interface

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   Worker        │
│   React/TS      │◄──►│   FastAPI       │◄──►│   Celery        │
│   Port 3000     │    │   Port 8000     │    │   Background    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │     Redis       │
                    │   Message Queue │
                    │   Port 6379     │
                    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Exoscale SOS  │    │     Nginx       │
│   DBaaS         │    │   S3 Storage    │    │   Reverse Proxy │
│   Port 5432     │    │   Files/Tiles   │    │   Port 80/443   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 **Deployment Instructions**

### **Step 1: Deploy Infrastructure**

1. **Configure Terraform Variables**:
   ```bash
   cd infra/terraform/environments/dev

   # Edit terraform.tfvars with your values:
   # - Replace SSH key with your public key
   # - Verify Exoscale API credentials
   # - Adjust instance size if needed
   ```

2. **Deploy to Exoscale**:
   ```bash
   terraform init
   terraform plan    # Review the deployment plan
   terraform apply   # Deploy infrastructure
   ```

3. **Note the Outputs**:
   - Server IP address
   - Database connection details
   - S3 bucket names to create

### **Step 2: Configure DNS**

Point your domain `community.haqnow.com` to the server IP address:
```
A record: community.haqnow.com → [SERVER_IP]
```

### **Step 3: Create S3 Buckets**

In the Exoscale console, create these buckets:
- `haqnow-community-dev-originals`
- `haqnow-community-dev-normalized`
- `haqnow-community-dev-derivatives`
- `haqnow-community-dev-exports`
- `haqnow-community-dev-trash`

### **Step 4: Deploy Application**

1. **SSH to Server**:
   ```bash
   ssh ubuntu@[SERVER_IP]
   ```

2. **Clone Repository**:
   ```bash
   git clone https://github.com/your-username/haqnow-community.git /opt/haqnow-community
   cd /opt/haqnow-community
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your database and S3 credentials
   ```

4. **Deploy Services**:
   ```bash
   cd deploy
   docker compose up -d --build
   ```

5. **Configure SSL** (Optional but recommended):
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d community.haqnow.com
   ```

### **Step 5: Initialize Admin User**

1. **Create First Admin User**:
   ```bash
   curl -X POST http://localhost:8000/auth/admin/users \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@haqnow.com",
       "full_name": "Admin User",
       "role": "admin",
       "password": "SecurePassword123!"
     }'
   ```

2. **Set up TOTP**: Use the returned TOTP secret with an authenticator app

## 🔧 **Configuration Files**

### **Environment Variables (.env)**
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# S3 Storage
S3_ENDPOINT=https://sos-ch-gva-2.exoscale.com
EXOSCALE_S3_ACCESS_KEY=your_access_key
EXOSCALE_S3_SECRET_KEY=your_secret_key
S3_BUCKET_ORIGINALS=haqnow-community-dev-originals

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Security
JWT_SECRET_KEY=your_jwt_secret_key_here
```

## 🧪 **Testing the Deployment**

### **Health Checks**
```bash
# API Health
curl http://[SERVER_IP]:8000/health

# Frontend
curl http://[SERVER_IP]:3000

# Full Stack via Nginx
curl http://community.haqnow.com
```

### **Functional Tests**
1. **Login**: Access the web interface and log in with admin credentials
2. **Upload Document**: Test document upload and processing
3. **Search**: Verify search functionality works
4. **Admin Panel**: Create users and API keys
5. **Document Viewer**: Open a document and test the viewer

## 📊 **Monitoring & Maintenance**

### **Service Status**
```bash
# Check all services
docker compose ps

# View logs
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
```

### **Database Backup**
The PostgreSQL DBaaS includes automatic backups. Manual backups can be created through the Exoscale console.

### **Scaling Considerations**
- **Horizontal**: Add more worker containers for processing
- **Vertical**: Upgrade instance types in Terraform
- **Storage**: Monitor S3 usage and costs

## 🔒 **Security Checklist**

- ✅ HTTPS enabled with SSL certificates
- ✅ Database credentials secured
- ✅ API keys with proper scopes
- ✅ TOTP MFA enforced for all users
- ✅ Security groups restrict access
- ✅ Regular security updates via cloud-init

## 🆘 **Troubleshooting**

### **Common Issues**

1. **Services won't start**: Check Docker logs and ensure all environment variables are set
2. **Database connection failed**: Verify DATABASE_URL and network connectivity
3. **File uploads fail**: Check S3 credentials and bucket permissions
4. **Processing jobs stuck**: Restart worker container and check Redis connection

### **Support Commands**
```bash
# Restart all services
docker compose restart

# Rebuild and restart
docker compose down && docker compose up -d --build

# Check system resources
htop
df -h
```

## 🎉 **Success!**

Your Haqnow Community platform is now live and ready for journalists to:
- Upload and process documents securely
- Search through document collections
- Collaborate with annotations and comments
- Manage access with role-based permissions
- Export processed documents

**Platform URL**: https://community.haqnow.com
**Admin Panel**: https://community.haqnow.com/admin
**API Documentation**: https://community.haqnow.com/api/docs

---

*For technical support or questions, refer to the codebase documentation or contact the development team.*
