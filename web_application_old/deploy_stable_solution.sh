#!/bin/bash

# Stable Deployment Script with Process Management
# This script deploys the pesticide search app with proper systemd services and monitoring

echo "🚀 Deploying Stable Pesticide Search Application"
echo "================================================"

# Configuration
EC2_IP="18.188.50.246"
EC2_USER="ubuntu"
KEY_PATH="web_application/pesticide-search-key-new.pem"

echo "📋 Configuration:"
echo "   EC2 IP: $EC2_IP"
echo "   User: $EC2_USER"
echo "   Key: $KEY_PATH"
echo ""

# Verify SSH key
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key not found at $KEY_PATH"
    exit 1
fi

chmod 400 "$KEY_PATH"

# Test connection
echo "🔍 Testing SSH connection..."
if ! ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "❌ Error: Cannot connect to EC2 instance"
    exit 1
fi

echo "✅ SSH connection successful!"

# Deploy the stable solution
echo "🔧 Deploying stable solution with process management..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    echo "🔧 Step 1: Stopping all existing services"
    echo "========================================="
    
    # Stop any existing processes
    sudo systemctl stop pesticide-search 2>/dev/null || true
    sudo systemctl stop health-monitor 2>/dev/null || true
    pkill -f "pesticide_search.py" || true
    pkill -f "health_monitor.py" || true
    sleep 3
    
    echo ""
    echo "🔧 Step 2: Setting up application directory"
    echo "=========================================="
    
    # Navigate to application directory
    cd /home/ubuntu/pesticide-search
    
    # Ensure virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment and install dependencies
    source venv/bin/activate
    pip install --upgrade pip
    pip install flask requests openpyxl
    
    echo ""
    echo "🔧 Step 3: Installing systemd services"
    echo "====================================="
    
    # Copy service files to systemd directory
    sudo cp pesticide-search.service /etc/systemd/system/
    sudo cp health-monitor.service /etc/systemd/system/
    
    # Reload systemd to recognize new services
    sudo systemctl daemon-reload
    
    # Enable services to start on boot
    sudo systemctl enable pesticide-search
    sudo systemctl enable health-monitor
    
    echo "✅ Systemd services installed and enabled"
    
    echo ""
    echo "🔧 Step 4: Starting services"
    echo "==========================="
    
    # Start the main application service
    sudo systemctl start pesticide-search
    
    # Wait for application to start
    echo "Waiting for application to start..."
    sleep 10
    
    # Check if application started successfully
    if sudo systemctl is-active --quiet pesticide-search; then
        echo "✅ Pesticide search service started successfully"
        
        # Test the application
        if curl -s http://localhost:5001/health > /dev/null 2>&1; then
            echo "✅ Application health check passed"
        else
            echo "⚠️  Application started but health check failed"
        fi
    else
        echo "❌ Failed to start pesticide search service"
        echo "Service status:"
        sudo systemctl status pesticide-search --no-pager -l
        echo "Application logs:"
        journalctl -u pesticide-search --no-pager -l -n 20
        exit 1
    fi
    
    # Start the health monitor
    sudo systemctl start health-monitor
    
    if sudo systemctl is-active --quiet health-monitor; then
        echo "✅ Health monitor started successfully"
    else
        echo "⚠️  Health monitor failed to start (non-critical)"
        sudo systemctl status health-monitor --no-pager -l
    fi
    
    echo ""
    echo "🔧 Step 5: Configuring nginx"
    echo "==========================="
    
    # Create nginx configuration
    sudo tee /etc/nginx/sites-available/default > /dev/null << 'NGINX_CONFIG'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    # Increase client body size for file uploads
    client_max_body_size 10M;
    
    # Main application proxy
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5001/health;
        proxy_set_header Host $host;
        access_log off;
    }
    
    # Static files (if any)
    location /static/ {
        alias /home/ubuntu/pesticide-search/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_CONFIG
    
    # Test nginx configuration
    if sudo nginx -t; then
        echo "✅ Nginx configuration is valid"
        
        # Restart nginx
        sudo systemctl restart nginx
        
        if sudo systemctl is-active --quiet nginx; then
            echo "✅ Nginx started successfully"
        else
            echo "❌ Nginx failed to start"
            sudo systemctl status nginx --no-pager -l
        fi
    else
        echo "❌ Nginx configuration is invalid"
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 6: Final verification"
    echo "============================"
    
    # Check all services
    echo "Service Status:"
    echo "Pesticide Search: $(sudo systemctl is-active pesticide-search)"
    echo "Health Monitor: $(sudo systemctl is-active health-monitor)"
    echo "Nginx: $(sudo systemctl is-active nginx)"
    
    # Check ports
    echo ""
    echo "Port Status:"
    echo "Port 80: $(sudo netstat -tlnp | grep :80 > /dev/null && echo 'listening' || echo 'not listening')"
    echo "Port 5001: $(sudo netstat -tlnp | grep :5001 > /dev/null && echo 'listening' || echo 'not listening')"
    
    # Test the full stack
    echo ""
    echo "Testing full stack..."
    if curl -s http://localhost/health > /dev/null 2>&1; then
        echo "✅ Full stack (nginx -> Flask) working"
    else
        echo "❌ Full stack test failed"
    fi
    
    # Show recent logs
    echo ""
    echo "📊 Recent Application Logs:"
    journalctl -u pesticide-search --no-pager -l -n 10
    
    echo ""
    echo "📊 System Resources:"
    echo "Memory usage:"
    free -h
    echo ""
    echo "Disk usage:"
    df -h /
EOF

echo ""
echo "🎉 Stable Deployment Completed!"
echo ""
echo "🌐 Your application is now available at:"
echo "   http://$EC2_IP"
echo "   http://$EC2_IP/pesticide-database"
echo ""
echo "🔧 Service Management Commands:"
echo "   Check status: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'sudo systemctl status pesticide-search health-monitor nginx'"
echo "   View logs: ssh -i $EC2_USER@$EC2_IP 'journalctl -u pesticide-search -f'"
echo "   Restart app: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'sudo systemctl restart pesticide-search'"
echo "   Check health: curl http://$EC2_IP/health"
echo ""
echo "📋 Monitoring Features:"
echo "   ✅ Automatic restart on crash"
echo "   ✅ Health monitoring with alerts"
echo "   ✅ Memory limits to prevent OOM"
echo "   ✅ Proper logging and error tracking"
echo "   ✅ Service management with systemd"
echo ""
echo "🧪 Test the deployment:"
echo "   Health check: curl http://$EC2_IP/health"
echo "   API stats: curl http://$EC2_IP/api/stats"
echo "   Web interface: http://$EC2_IP/pesticide-database"

