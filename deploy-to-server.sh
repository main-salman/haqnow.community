#!/bin/bash
set -e

# Haqnow Community Platform - Server Deployment Script
echo "🚀 Deploying Haqnow Community Platform to Exoscale..."

SERVER_IP="185.19.30.32"
SSH_KEY="~/.ssh/haqnow_deploy_key"

echo "📡 Connecting to server: $SERVER_IP"

# Copy environment file and project files to server
echo "📁 Copying project files..."
scp -i $SSH_KEY .env ubuntu@$SERVER_IP:/tmp/
scp -i $SSH_KEY -r . ubuntu@$SERVER_IP:/tmp/haqnow-community/

# SSH to server and deploy
echo "🔧 Deploying on server..."
ssh -i $SSH_KEY ubuntu@$SERVER_IP << 'EOF'
    set -e

    echo "📦 Setting up application directory..."
    sudo mkdir -p /opt/haqnow-community
    sudo cp -r /tmp/haqnow-community/* /opt/haqnow-community/
    sudo cp /tmp/.env /opt/haqnow-community/
    sudo chown -R ubuntu:ubuntu /opt/haqnow-community

    cd /opt/haqnow-community

    echo "🐳 Starting Docker services..."
    cd deploy
    docker compose down || true
    docker compose up -d --build

    echo "🌐 Configuring Nginx..."
    sudo ln -sf /etc/nginx/sites-available/haqnow-community /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx

    echo "✅ Deployment complete!"
    echo "🌍 Frontend: http://$(curl -s ifconfig.me)"
    echo "🔧 API: http://$(curl -s ifconfig.me):8000"
    echo "❤️  Health: http://$(curl -s ifconfig.me):8000/health"

    # Show running containers
    echo "📊 Running containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
EOF

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Configure DNS: Point community.haqnow.com to 159.100.241.129"
echo "2. Set up SSL: ssh -i $SSH_KEY ubuntu@$SERVER_IP"
echo "3. Run: sudo certbot --nginx -d community.haqnow.com"
echo ""
echo "🌐 Your platform will be live at: https://community.haqnow.com"
