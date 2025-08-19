# Haqnow Community Platform

A community document platform backend built with FastAPI, SQLAlchemy, and modern Python technologies.

## Architecture Quick Map (for humans and tools)

Use this section to quickly locate code without scanning the whole repo.

- Backend API (FastAPI): `backend/app/`
  - App entry: `backend/app/main.py`
  - Data models: `backend/app/models.py`
  - Schemas/validation: `backend/app/schemas.py`
  - Security/auth: `backend/app/security.py`, `backend/app/routes_auth.py`
  - Documents: `backend/app/routes_documents.py`, `backend/app/processing.py`, `backend/app/tasks.py`, `backend/app/s3_client.py`
  - Search/RAG: `backend/app/routes_search.py`, `backend/app/rag.py`
  - Config/DB: `backend/app/config.py`, `backend/app/db.py`, `backend/app/celery_app.py`
  - Tests: `backend/tests/`
- Frontend (Vite + React + TS): `frontend/src/`
  - App bootstrap: `frontend/src/main.tsx`, `frontend/src/App.tsx`
  - Pages: `frontend/src/pages/*.tsx`
  - Components: `frontend/src/components/*.tsx`
  - API layer: `frontend/src/services/api.ts`, `frontend/src/services/auth.ts`
  - Styles: `frontend/src/index.css`, `frontend/tailwind.config.js`
- Deployment & Ops
  - Local dev orchestration: `start-local.sh`, `stop-local.sh`
  - Docker compose (server deploy): `deploy/docker-compose.yml`, `deploy/haqnow-community.nginx`
  - Server deploy script: `deploy-to-server.sh`
  - Infra as code: `infra/terraform/` (modules + environments)
- Storage and data
  - Local uploads: `backend/uploads/`
  - Local vector/db assets: `backend/chroma_db/` (binary data; do not scan)

See `architecture.txt` for a deeper end-to-end system description.

## Common Files and Tasks Map

This map lists frequent tasks and the primary files to touch. Prefer these files before exploring widely.

- Authentication/MFA/JWT
  - Backend: `backend/app/security.py`, `backend/app/routes_auth.py`, `backend/app/schemas.py`
  - Frontend: `frontend/src/services/auth.ts`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/components/MfaSetup.tsx`
  - Tests: `backend/tests/test_auth.py`, `backend/tests/test_api_keys.py`
- Document upload, processing, and viewing
  - Backend: `backend/app/routes_documents.py`, `backend/app/processing.py`, `backend/app/tasks.py`, `backend/app/s3_client.py`, `backend/app/export.py`, `backend/app/redaction.py`
  - Frontend: `frontend/src/components/DocumentUpload.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/pages/DocumentViewerPage.tsx`, `frontend/src/components/DocumentViewer.tsx`
  - Tests: `backend/tests/test_documents.py`, `backend/tests/test_processing.py`, `backend/tests/test_processing_integration.py`, `backend/tests/test_comprehensive_document_management.py`
- Search and RAG
  - Backend: `backend/app/routes_search.py`, `backend/app/rag.py`
  - Frontend: search UI elements live in `frontend/src/pages/DashboardPage.tsx` (and related components)
  - Tests: covered in integration suites where applicable
- API integration layer (frontend↔backend)
  - Frontend: `frontend/src/services/api.ts`
  - Shared types/interfaces: colocated within frontend `services/` and `pages/`
- Configuration & environment
  - Backend settings: `backend/app/config.py`, `.env`
  - Local dev scripts: `start-local.sh`, `stop-local.sh`
  - Deployment: `deploy-to-server.sh`, `deploy/docker-compose.yml`
- Database/ORM
  - Models and migrations starting point: `backend/app/models.py` (alembic config not included in this repo snapshot)

When adding features, add or update tests in `backend/tests/` alongside the feature area.

## Architecture

The platform follows a modular architecture with clear separation of concerns:

- **Backend API**: FastAPI-based REST API with authentication and document management
- **Database**: SQLAlchemy ORM with support for multiple database backends
- **Authentication**: JWT-based authentication with optional 2FA support
- **File Storage**: S3-compatible storage for document uploads
- **Background Tasks**: Celery with Redis for asynchronous processing
- **Infrastructure**: Terraform-managed cloud infrastructure

## Features

### Current Features
- User authentication and authorization
- JWT token management with refresh tokens
- Document upload and management
- S3-compatible file storage
- Background task processing
- API key management
- Health monitoring endpoints

### Authentication System
- User registration and login
- JWT access and refresh tokens
- Optional TOTP-based 2FA
- Secure password hashing with bcrypt
- API key authentication for service-to-service communication

### Document Management
- File upload to S3-compatible storage
- Document metadata management
- Access control and permissions
- Background processing for document analysis
 - Pixel-level comments and redactions
   - Comments: anchored to page and pixel coordinates (image space)
   - Redactions: rectangle overlays in image pixels (300 DPI), black only
   - Real-time sync for comments/redactions via Socket.IO
   - Redaction lock: first editor wins; others see a notice
   - Export burn-in: redactions are burned into exported PDFs/images at 300 DPI for immutability

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and ORM
- **Pydantic**: Data validation using Python type annotations
- **JWT**: JSON Web Tokens for authentication
- **Celery**: Distributed task queue
- **Redis**: In-memory data store for caching and task queue
- **Boto3**: AWS SDK for S3 storage integration

### Infrastructure
- **Terraform**: Infrastructure as Code
- **Docker**: Containerization
- **AWS/Cloud**: Cloud infrastructure deployment

## Project Structure

```
haqnow.community/
├── backend/                 # FastAPI backend application
│   ├── app/                # Application code
│   │   ├── main.py        # FastAPI application entry point
│   │   ├── models.py      # SQLAlchemy database models
│   │   ├── schemas.py     # Pydantic schemas for validation
│   │   ├── routes_*.py    # API route handlers
│   │   ├── security.py    # Authentication and security utilities
│   │   └── tasks.py       # Celery background tasks
│   ├── tests/             # Test suite
│   └── pyproject.toml     # Python dependencies and configuration
├── infra/                 # Infrastructure as Code
│   └── terraform/         # Terraform configurations
│       ├── modules/       # Reusable Terraform modules
│       └── environments/  # Environment-specific configurations
├── deploy/                # Deployment configurations
└── docs/                  # Documentation
```

### Cursor/tooling note
- Tools should prefer the "Architecture Quick Map" and "Common Files and Tasks Map" above to scope searches narrowly.
- Avoid scanning binary directories like `backend/chroma_db/`, `backend/uploads/`, and large PDFs in repo root unless explicitly relevant.

## Development Setup

### Prerequisites
- Python 3.11+
- Poetry for dependency management
- Redis server
- Node.js and npm
- PostgreSQL (or SQLite for development)

### Quick Start (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd haqnow.community
```

2. Run the automated setup:
```bash
./setup-dev.sh
```

3. Start all services with a single command:
```bash
./start-local.sh
```

This will start:
- Redis server (if not already running)
- Backend API server on http://localhost:8000
- Frontend development server on http://localhost:3000

4. Stop all services:
```bash
./stop-local.sh
```

### Manual Installation

If you prefer to set up manually:

1. Install backend dependencies:
```bash
cd backend
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run database migrations:
```bash
poetry run alembic upgrade head
```

5. Start the development server:
```bash
poetry run uvicorn app.main:app --reload
```

### Running Tests

```bash
cd backend
poetry run pytest
```

To run only redaction pixel tests:
```bash
cd backend
poetry run pytest tests/test_redaction_pixels.py -q
```

Playwright E2E (optional, requires Playwright installed):
```bash
cd backend
poetry run pytest tests/test_playwright_redactions_comments.py -q
```

Frontend build (type check):
```bash
cd frontend
npm install
npm run build
```

### Running with Docker

```bash
docker-compose -f deploy/docker-compose.yml up
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints (documents)
- `POST /documents/{id}/comments` — add comment with `{ page_number, x_position, y_position, content }`
- `PUT /documents/{id}/comments/{comment_id}` — update comment pixel position/content
- `DELETE /documents/{id}/comments/{comment_id}` — delete comment (hard delete)
- `POST /documents/{id}/redactions` — add redaction `{ page_number, x_start, y_start, x_end, y_end, reason? }`
- `PUT /documents/{id}/redactions/{redaction_id}` — move/resize (pixel values)
- `DELETE /documents/{id}/redactions/{redaction_id}` — delete redaction
- `POST /documents/{id}/pages/{page}/redact` — burn-in page redactions
- `POST /documents/{id}/export` — export PDF/images with `include_redacted=true` to burn-in

## Environment Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/dbname

# JWT Configuration
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# S3 Storage
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0
```

## Deployment

### Infrastructure Deployment

1. Navigate to the Terraform environment:
```bash
cd infra/terraform/environments/dev
```

2. Initialize and apply Terraform:
```bash
terraform init
terraform plan
terraform apply
```

### Application Deployment

The application can be deployed using Docker containers with the provided docker-compose configuration.

## Contributing

1. Follow the rules defined in `.cursorrules`
2. Write tests for all new features
3. Update documentation with changes
4. Ensure all tests pass before committing
5. Use conventional commit messages

## Testing Strategy

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test API endpoints and database operations
- **Authentication Tests**: Verify security and access control
- **Document Processing Tests**: Test file upload and processing workflows

## Security Considerations

- All API endpoints require authentication except health checks
- Passwords are hashed using bcrypt
- JWT tokens have configurable expiration
- File uploads are validated and stored securely
- API keys provide service-to-service authentication

## Monitoring and Health

- Health check endpoint: `/health`
- Application metrics and logging
- Background task monitoring via Celery

## License

[Add your license information here]

## Support

[Add support contact information here]


🚀 Ready for Development:
The repository is now fully set up with:
✅ Automated testing on every commit
✅ Code quality enforcement
✅ Documentation requirements
✅ CI/CD pipeline that will run on every push/PR
✅ Complete development environment setup
Anyone can now clone the repository and run ./setup-dev.sh to get started with development, and all the quality gates we established will be automatically enforced!
