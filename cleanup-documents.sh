#!/bin/bash

# Remote Document Cleanup Script
# This script runs the cleanup on the remote server using SSH

echo "🧹 Haqnow Community - Remote Document Cleanup"
echo "=============================================="
echo ""

# Check if we're in the right directory
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found. Please run this script from the project root directory."
    exit 1
fi

if [ ! -f "backend/cleanup_documents.py" ]; then
    echo "❌ Error: cleanup_documents.py not found. Please run this script from the project root directory."
    exit 1
fi

# Run the Python cleanup script
python3 backend/cleanup_documents.py
