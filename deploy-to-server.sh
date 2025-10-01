#!/bin/bash
set -e

# Haqnow Community Platform - Server Deployment Script
# Following cursor rule: Copy .env, commit to git, pull from GitHub on server
echo "🚀 Deploying Haqnow Community Platform to Exoscale..."

SERVER_IP="${SERVER_IP:-91.92.153.62}"
# Use absolute path to avoid tilde expansion issues in non-interactive contexts
SSH_KEY="$HOME/.ssh/haqnow_deploy_key"
REPO_URL="https://github.com/main-salman/haqnow.community.git"

echo "📡 Connecting to server: $SERVER_IP"

# Step 0: Commit and push local changes (tests must be green before you run this)
echo "🧭 Ensuring local changes are committed and pushed..."
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "📝 Committing local changes..."
    git add -A
    git commit -m "chore(deploy): sync local changes before server deploy"
else
    echo "✅ No local changes to commit"
fi
echo "⬆️  Pushing to GitHub..."
git push origin main

# Step 1: Copy .env file to server
echo "📁 Copying .env file to server..."
scp -i "$SSH_KEY" .env ubuntu@$SERVER_IP:/tmp/

# Step 2: SSH to server and deploy from GitHub
echo "🔧 Deploying from GitHub on server..."
ssh -i "$SSH_KEY" ubuntu@$SERVER_IP << EOF
    set -e

    echo "📦 Setting up application directory..."
    sudo mkdir -p /opt/haqnow-community
    sudo chown -R ubuntu:ubuntu /opt/haqnow-community

    # Clone or update repository from GitHub
    if [ -d "/opt/haqnow-community/.git" ]; then
        echo "🔄 Updating existing repository..."
        cd /opt/haqnow-community
        git fetch origin
        git reset --hard origin/main
        git pull origin main
    else
        echo "📥 Cloning repository from GitHub..."
        git clone $REPO_URL /opt/haqnow-community
        cd /opt/haqnow-community
    fi

    # Copy environment file
    echo "📋 Setting up environment configuration..."
    cp /tmp/.env /opt/haqnow-community/

    # Make scripts executable
    chmod +x start-local.sh deploy-to-server.sh test-all-features.sh || true

    # Set up testing environment
    echo "🧪 Setting up testing environment..."
    mkdir -p /opt/haqnow-community/backend/uploads
    mkdir -p /opt/haqnow-community/backend/chroma_db
    mkdir -p /opt/haqnow-community/test_env

    echo "🐳 Starting Docker services..."
    cd deploy
    docker-compose down || true
    docker-compose up -d --build

    echo "🌐 Configuring Nginx..."
    sudo cp haqnow-community.nginx /etc/nginx/sites-available/haqnow-community
    sudo ln -sf /etc/nginx/sites-available/haqnow-community /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx || sudo systemctl restart nginx

    echo "✅ Deployment complete!"
    echo "🌍 Frontend: http://\$(curl -s ifconfig.me)"
    echo "🔧 API: http://\$(curl -s ifconfig.me):8000"
    echo "❤️  Health: http://\$(curl -s ifconfig.me):8000/health"

    # Show running containers
    echo "📊 Running containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
EOF

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. ✅ DNS configured: community.haqnow.com → 159.100.241.129"
echo "2. Set up SSL: ssh -i $SSH_KEY ubuntu@$SERVER_IP"
echo "3. Run: sudo certbot --nginx -d community.haqnow.com"
echo ""
echo "🌐 Your platform will be live at: https://community.haqnow.com"
