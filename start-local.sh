#!/bin/bash

# Start Local Development Script for Haqnow Community Platform
# This script starts all necessary services to run the application locally

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}🚀 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill processes on specific ports
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port)
    if [ ! -z "$pids" ]; then
        print_warning "Killing existing processes on port $port"
        kill -9 $pids 2>/dev/null || true
        sleep 2
    fi
}

# Function to cleanup on script interruption
cleanup() {
    print_status "Cleaning up processes..."

    # Kill tail process if running
    if [ ! -z "$TAIL_PID" ]; then
        kill $TAIL_PID 2>/dev/null || true
    fi

    # Kill Celery worker
    if [ ! -z "$CELERY_PID" ]; then
        kill $CELERY_PID 2>/dev/null || true
    fi

    # Kill backend server
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi

    # Kill frontend server
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi

    # Kill any remaining processes on our ports
    kill_port 8000
    kill_port 3000

    print_success "Cleanup complete"
    exit 0
}

# Set up trap to cleanup only on interruption (not normal exit)
trap cleanup INT TERM

print_status "Starting Haqnow Community Platform locally..."

# Check if we're in the right directory
if [ ! -f "setup-dev.sh" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Kill any existing processes on our ports
kill_port 8000
kill_port 3000

# 1. Check and start Docker if needed
print_status "Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    print_warning "Docker is not running. Starting Docker..."
    open -a Docker
    print_status "Waiting for Docker to start..."

    # Wait up to 60 seconds for Docker to start
    for i in {1..60}; do
        if docker info >/dev/null 2>&1; then
            print_success "Docker started successfully"
            break
        fi
        if [ $i -eq 60 ]; then
            print_error "Docker failed to start within 60 seconds. Please start Docker manually and try again."
            exit 1
        fi
        sleep 1
    done
else
    print_success "Docker is already running"
fi

# 2. Load environment from .env for Exoscale DB/SOS configuration
print_status "Loading environment from .env"
if [ -f ".env" ]; then
    # Export all variables from .env
    set -a
    source ./.env
    set +a
    print_success ".env loaded"
else
    print_warning ".env not found at project root. Ensure DATABASE_URL and S3 credentials are set in your environment."
fi

# 2.1 Ensure DB connectivity (Exoscale) - if blocked, establish SSH tunnel via server and override DATABASE_URL
print_status "Checking Exoscale DB connectivity..."
# Parse DB host/port/user/pass/db from DATABASE_URL
DB_HOST=$(python3 -c 'import os,urllib.parse as u; r=u.urlparse(os.environ.get("DATABASE_URL","")); print(r.hostname or "")' 2>/dev/null)
DB_PORT=$(python3 -c 'import os,urllib.parse as u; r=u.urlparse(os.environ.get("DATABASE_URL","")); print(r.port or "")' 2>/dev/null)
DB_USER=$(python3 -c 'import os,urllib.parse as u; r=u.urlparse(os.environ.get("DATABASE_URL","")); print(r.username or "")' 2>/dev/null)
DB_PASS=$(python3 -c 'import os,urllib.parse as u; r=u.urlparse(os.environ.get("DATABASE_URL","")); print(r.password or "")' 2>/dev/null)
DB_NAME=$(python3 -c 'import os,urllib.parse as u; r=u.urlparse(os.environ.get("DATABASE_URL","")); print((r.path or "/")[1:])' 2>/dev/null)
DB_QUERY=$(python3 -c 'import os,urllib.parse as u; r=u.urlparse(os.environ.get("DATABASE_URL","")); print(r.query or "")' 2>/dev/null)

TUNNEL_PORT=55432
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    # Quick TCP probe
    if ! python3 - "$DB_HOST" "$DB_PORT" 2>/dev/null <<'PY'
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket()
s.settimeout(2)
try:
    s.connect((host, port))
    print("OK")
    sys.exit(0)
except Exception:
    sys.exit(1)
finally:
    try:
        s.close()
    except Exception:
        pass
PY
    then
        print_warning "DB not reachable directly. Creating SSH tunnel via server $SERVER_IP..."
        # Kill any existing tunnel on the same local port
        kill_port $TUNNEL_PORT || true
        # Create tunnel: local TUNNEL_PORT -> DB_HOST:DB_PORT via server
        ssh -i "$HOME/.ssh/haqnow_deploy_key" -f -N -L $TUNNEL_PORT:$DB_HOST:$DB_PORT ubuntu@${SERVER_IP} || true
        # Override DATABASE_URL to use localhost and tunnel port
        if [ -n "$DB_QUERY" ]; then
            export DATABASE_URL="postgres://${DB_USER}:${DB_PASS}@127.0.0.1:${TUNNEL_PORT}/${DB_NAME}?${DB_QUERY}"
        else
            export DATABASE_URL="postgres://${DB_USER}:${DB_PASS}@127.0.0.1:${TUNNEL_PORT}/${DB_NAME}"
        fi
        print_success "DB tunnel established on localhost:${TUNNEL_PORT}"
    else
        print_success "Exoscale DB reachable directly"
    fi
fi

# Sanity hints for local dev using Exoscale
if [[ -z "${DATABASE_URL}" ]]; then
    print_warning "DATABASE_URL is not set. Set it to your Exoscale Postgres connection string in .env."
fi
if [[ -z "${EXOSCALE_S3_ACCESS_KEY}" || -z "${EXOSCALE_S3_SECRET_KEY}" || -z "${S3_ENDPOINT}" ]]; then
    print_warning "Exoscale SOS variables (EXOSCALE_S3_ACCESS_KEY, EXOSCALE_S3_SECRET_KEY, S3_ENDPOINT) are not fully set."
fi

# 3. Start Docker services (Redis, Ollama)
print_status "Starting Docker services..."
cd deploy
if ! docker-compose ps | grep -q "Up"; then
    print_status "Starting Redis and Ollama with Docker Compose..."
    docker-compose up -d redis ollama
    sleep 10
    print_success "Docker services started successfully"
else
    print_success "Docker services are already running"
fi
cd ..

# 4. Initialize Database (against configured DATABASE_URL)
print_status "Initializing database..."
cd backend

# Check if Poetry is available
if ! command -v poetry >/dev/null 2>&1; then
    print_error "Poetry is not installed. Please run ./setup-dev.sh first"
    exit 1
fi

# Check if dependencies are installed and install them
print_status "Ensuring dependencies are installed..."
poetry install

# Activate virtual environment and check if uvicorn is available
if ! poetry run python -c "import uvicorn" 2>/dev/null; then
    print_error "uvicorn not found in virtual environment. Reinstalling dependencies..."
    poetry install --no-cache
fi

# Run database migrations/setup
print_status "Setting up database tables..."
# Append any DB init errors to backend.log to avoid noisy console failures
poetry run python -c "from app.db import Base, engine; from app import models; Base.metadata.create_all(bind=engine)" >> backend.log 2>&1 || true

# Ensure local directories exist for fallbacks (tiles/previews if S3 not reachable)
mkdir -p uploads
mkdir -p chroma_db

# Start Celery worker in background (uses Redis and Exoscale DB/SOS via env)
print_status "Starting Celery worker..."
poetry run celery -A app.tasks worker --loglevel=info > celery.log 2>&1 &
CELERY_PID=$!

# Start backend server in background
print_status "Starting FastAPI server on http://localhost:8000"
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start by polling health endpoint (up to 30s)
print_status "Waiting for backend health..."
for i in {1..30}; do
    if curl -sSf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        print_success "Backend API server started successfully"
        print_success "API Documentation: http://localhost:8000/docs"
        print_success "Health Check: http://localhost:8000/health"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        print_error "Failed to start backend server (health check timed out). See backend/backend.log"
        tail -n 200 backend.log || true
        exit 1
    fi
done

# 5. Start Frontend
print_status "Starting Frontend development server..."
cd ../frontend

# Check if Node.js is available
if ! command -v npm >/dev/null 2>&1; then
    print_error "npm is not installed. Please install Node.js first"
    exit 1
fi

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    print_warning "Node modules not found. Installing dependencies..."
    npm install
fi

# Start frontend server in background
print_status "Starting Vite development server on http://localhost:3000"
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 5
if check_port 3000; then
    print_success "Frontend development server started successfully"
else
    print_error "Failed to start frontend server. Check frontend/frontend.log for details"
    cat frontend.log
    exit 1
fi

# 5. Display status and URLs
echo ""
print_success "🎉 All services started successfully!"
echo ""
echo -e "${GREEN}📱 Frontend Application:${NC}     http://localhost:3000"
echo -e "${GREEN}🔧 API Documentation:${NC}       http://localhost:8000/docs"
echo -e "${GREEN}❤️  Health Check:${NC}           http://localhost:8000/health"
echo ""
print_status "Services running with PIDs:"
echo -e "  Celery Worker:      PID $CELERY_PID"
echo -e "  Backend (FastAPI):  PID $BACKEND_PID"
echo -e "  Frontend (Vite):    PID $FRONTEND_PID"
echo ""
print_warning "Press Ctrl+C to stop all services"
echo ""

# 6. Show real-time logs
print_status "Showing combined logs (Ctrl+C to stop):"
echo ""

# Follow logs from all services (create log files if they don't exist)
cd ..
touch backend/backend.log backend/celery.log frontend/frontend.log

# Follow logs from all services
tail -f backend/backend.log backend/celery.log frontend/frontend.log &
TAIL_PID=$!

# Show options to user
echo -e "${YELLOW}💡 Tip:${NC} Close this terminal window to keep services running in background"
echo -e "${YELLOW}💡 Tip:${NC} Use ./stop-local.sh to stop all services later"
echo ""

# Wait for user to press Ctrl+C (which will trigger cleanup)
wait $TAIL_PID 2>/dev/null || true
