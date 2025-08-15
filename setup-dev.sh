#!/bin/bash

# Development Setup Script for Haqnow Community Platform
# This script sets up the development environment with all necessary tools and hooks

set -e

echo "🚀 Setting up Haqnow Community Platform development environment..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] && [ ! -d "backend" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Navigate to backend directory
cd backend

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Please install Poetry first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

echo "📦 Installing Python dependencies..."
poetry install

# Go back to project root
cd ..

# Install pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
cd backend
poetry run pre-commit install
cd ..

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    echo "⚙️  Creating .env file..."
    cat > backend/.env << EOF
# Database Configuration
DATABASE_URL=sqlite:///./dev.db

# JWT Configuration
SECRET_KEY=dev-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis Configuration (for Celery)
REDIS_URL=redis://localhost:6379/0

# S3 Configuration (for file storage)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name

# Optional: Enable debug mode
DEBUG=true
EOF
    echo "✅ Created backend/.env file. Please update it with your actual configuration."
else
    echo "✅ .env file already exists"
fi

# Initialize git repository if not already initialized
if [ ! -d ".git" ]; then
    echo "🔄 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit: Setup development environment with automated testing and documentation rules"
else
    echo "✅ Git repository already initialized"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Update backend/.env with your actual configuration"
echo "2. Start Redis server: redis-server"
echo "3. Run the development server: cd backend && poetry run uvicorn app.main:app --reload"
echo "4. Run tests: cd backend && poetry run pytest"
echo "5. View API docs at: http://localhost:8000/docs"
echo ""
echo "📋 Remember the rules:"
echo "• Every new feature MUST include automated tests"
echo "• Update README.md with new features and architecture changes"
echo "• Tests run automatically on every commit"
echo "• Follow the guidelines in .cursorrules"
echo ""
echo "Happy coding! 🚀"
