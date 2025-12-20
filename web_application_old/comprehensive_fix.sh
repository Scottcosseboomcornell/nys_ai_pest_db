#!/bin/bash

# Comprehensive Fix Script for 502 Bad Gateway
# This script addresses all common issues with nginx + Flask setup

echo "🔧 Comprehensive Fix for 502 Bad Gateway"
echo "========================================"

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="$1"

if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./comprehensive_fix.sh /path/to/your/pesticide-search-key-new.pem"
    exit 1
fi

if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key file not found at $KEY_PATH"
    exit 1
fi

chmod 400 "$KEY_PATH"

echo "🔍 Testing SSH connection..."
if ! ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "❌ Error: Cannot connect to EC2 instance"
    exit 1
fi

echo "✅ SSH connection successful!"

# Comprehensive fix
echo "🔧 Applying comprehensive fix..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    echo "🔧 Step 1: Complete system cleanup"
    echo "================================="
    
    # Stop all services
    sudo systemctl stop nginx
    pkill -f "pesticide_search.py" || true
    pkill -f "python.*pesticide" || true
    sleep 3
    
    echo ""
    echo "🔧 Step 2: Install missing tools"
    echo "==============================="
    
    # Install net-tools for netstat
    sudo apt update
    sudo apt install -y net-tools
    
    echo ""
    echo "🔧 Step 3: Setup Flask application"
    echo "================================="
    
    cd /home/ubuntu/pesticide-search
    
    # Ensure virtual environment exists
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # Install all required packages
    pip install flask requests
    
    # Check if application file exists
    if [ ! -f "pesticide_search.py" ]; then
        echo "❌ Error: pesticide_search.py not found"
        exit 1
    fi
    
    # Check if data directory exists
    if [ ! -d "altered_json" ] || [ -z "$(ls -A altered_json)" ]; then
        echo "❌ Error: altered_json directory is missing or empty"
        echo "Available directories:"
        ls -la
        exit 1
    fi
    
    echo "✅ Application files verified"
    
    echo ""
    echo "🔧 Step 4: Start Flask application"
    echo "================================="
    
    # Start Flask application with explicit port
    nohup python pesticide_search.py > app.log 2>&1 &
    
    # Wait for startup
    sleep 10
    
    # Check if Flask is running
    if pgrep -f "pesticide_search.py" > /dev/null; then
        echo "✅ Flask application started"
        echo "Process ID: $(pgrep -f 'pesticide_search.py')"
    else
        echo "❌ Flask application failed to start"
        echo "Logs:"
        cat app.log
        exit 1
    fi
    
    # Test Flask locally
    echo "Testing Flask application locally..."
    if curl -s http://localhost:5001/api/stats > /dev/null 2>&1; then
        echo "✅ Flask responding on port 5001"
    else
        echo "❌ Flask not responding on port 5001"
        echo "Checking what's listening:"
        netstat -tlnp | grep python || echo "No Python processes listening"
        echo "Recent logs:"
        tail -20 app.log
    fi
    
    echo ""
    echo "🔧 Step 5: Configure nginx properly"
    echo "=================================="
    
    # Create a clean nginx configuration
    sudo tee /etc/nginx/sites-available/default > /dev/null << 'NGINX_CONFIG'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    # Proxy all requests to Flask
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
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Static files (if needed)
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
    else
        echo "❌ Nginx configuration is invalid"
        sudo nginx -t
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 6: Start nginx and verify"
    echo "================================"
    
    # Start nginx
    sudo systemctl start nginx
    sudo systemctl enable nginx
    
    # Wait a moment
    sleep 3
    
    # Check nginx status
    if sudo systemctl is-active --quiet nginx; then
        echo "✅ Nginx is running"
    else
        echo "❌ Nginx failed to start"
        sudo systemctl status nginx --no-pager -l
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 7: Final verification"
    echo "============================"
    
    # Check all services
    echo "Service Status:"
    echo "Nginx: $(sudo systemctl is-active nginx)"
    echo "Flask: $(pgrep -f 'pesticide_search.py' > /dev/null && echo 'running' || echo 'not running')"
    
    # Check ports
    echo ""
    echo "Port Status:"
    echo "Port 80: $(netstat -tlnp | grep :80 > /dev/null && echo 'listening' || echo 'not listening')"
    echo "Port 5001: $(netstat -tlnp | grep :5001 > /dev/null && echo 'listening' || echo 'not listening')"
    
    # Test endpoints
    echo ""
    echo "Testing Endpoints:"
    
    # Test nginx health
    if curl -s http://localhost/health > /dev/null 2>&1; then
        echo "✅ Nginx health check: OK"
    else
        echo "❌ Nginx health check: FAILED"
    fi
    
    # Test Flask through nginx
    if curl -s http://localhost/api/stats > /dev/null 2>&1; then
        echo "✅ Flask API through nginx: OK"
    else
        echo "❌ Flask API through nginx: FAILED"
    fi
    
    # Test main page
    if curl -s http://localhost/ > /dev/null 2>&1; then
        echo "✅ Main page through nginx: OK"
    else
        echo "❌ Main page through nginx: FAILED"
    fi
    
    echo ""
    echo "📊 Application Status:"
    echo "====================="
    echo "Flask process:"
    ps aux | grep pesticide_search.py | grep -v grep || echo "No Flask process found"
    echo ""
    echo "Recent Flask logs:"
    tail -10 app.log
    echo ""
    echo "Nginx error logs (if any):"
    sudo tail -5 /var/log/nginx/error.log 2>/dev/null || echo "No nginx errors"
EOF

echo ""
echo "🎉 Comprehensive Fix Completed!"
echo ""
echo "🌐 Your application should now be available at:"
echo "   http://$EC2_IP"
echo "   http://$EC2_IP/pesticide-database"
echo "   http://$EC2_IP/api/stats"
echo ""
echo "📋 Monitoring Commands:"
echo "   View Flask logs: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'"
echo "   View nginx logs: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'sudo tail -f /var/log/nginx/error.log'"
echo "   Check services: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'sudo systemctl status nginx && ps aux | grep python'"
echo ""
echo "🧪 Test Commands:"
echo "   curl http://$EC2_IP/health"
echo "   curl http://$EC2_IP/api/stats"
echo "   curl http://$EC2_IP/"


