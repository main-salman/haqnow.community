# Haqnow Community Platform

A community document platform backend built with FastAPI, SQLAlchemy, and modern Python technologies.

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

### Running with Docker

```bash
docker-compose -f deploy/docker-compose.yml up
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

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
