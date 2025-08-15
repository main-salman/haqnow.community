#!/bin/bash

# Stop Local Development Script for Haqnow Community Platform
# This script stops all services started by start-local.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}🛑 $1${NC}"
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

# Function to kill processes on specific ports
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ ! -z "$pids" ]; then
        print_warning "Killing processes on port $port"
        kill -9 $pids 2>/dev/null || true
        sleep 1
        print_success "Port $port cleared"
    else
        print_success "Port $port is already free"
    fi
}

print_status "Stopping Haqnow Community Platform services..."

# Kill processes on our ports
print_status "Stopping services on ports 8000 and 3000..."
kill_port 8000
kill_port 3000

# Stop Celery workers
print_status "Stopping Celery workers..."
pkill -f "celery.*app.tasks" 2>/dev/null || true

# Stop any remaining Python/Node processes related to our app
print_status "Stopping remaining application processes..."
pkill -f "uvicorn.*app.main" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

# Stop Docker services
print_status "Stopping Docker services..."
cd deploy 2>/dev/null || true
if [ -f "docker-compose.yml" ]; then
    docker-compose down
    print_success "Docker services stopped"
else
    print_warning "docker-compose.yml not found, skipping Docker cleanup"
fi
cd .. 2>/dev/null || true

# Clean up log files
print_status "Cleaning up log files..."
rm -f backend/backend.log backend/celery.log frontend/frontend.log 2>/dev/null || true
print_success "Log files cleaned up"

print_success "🎉 All services stopped successfully!"
echo ""
print_status "To start services again, run: ./start-local.sh"
