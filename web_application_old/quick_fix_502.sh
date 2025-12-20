#!/bin/bash

# Quick Fix for 502 Bad Gateway - Immediate Solution
# This script provides a quick fix while you implement the stable solution

echo "🚨 Quick Fix for 502 Bad Gateway"
echo "================================"

# Configuration
EC2_IP="18.188.50.246"
EC2_USER="ubuntu"
KEY_PATH="$1"

if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./quick_fix_502.sh /path/to/your/pesticide-search-key-new.pem"
    exit 1
fi

if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key file not found at $KEY_PATH"
    exit 1
fi

chmod 400 "$KEY_PATH"

echo "🔧 Applying quick fix..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    echo "🔧 Step 1: Stopping all services"
    sudo systemctl stop nginx 2>/dev/null || true
    pkill -f "pesticide_search.py" || true
    pkill -f "health_monitor.py" || true
    sleep 3
    
    echo ""
    echo "🔧 Step 2: Starting Flask application"
    cd /home/ubuntu/pesticide-search
    
    # Activate virtual environment
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        python3 -m venv venv
        source venv/bin/activate
        pip install flask requests openpyxl
    fi
    
    # Start Flask app in background
    nohup python pesticide_search.py > app.log 2>&1 &
    
    # Wait for startup
    sleep 10
    
    # Check if running
    if pgrep -f "pesticide_search.py" > /dev/null; then
        echo "✅ Flask application started"
    else
        echo "❌ Flask application failed to start"
        echo "Logs:"
        cat app.log
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 3: Configuring nginx"
    sudo tee /etc/nginx/sites-available/default > /dev/null << 'NGINX_CONFIG'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:5001/health;
        access_log off;
    }
}
NGINX_CONFIG
    
    # Test and start nginx
    if sudo nginx -t; then
        sudo systemctl start nginx
        echo "✅ Nginx configured and started"
    else
        echo "❌ Nginx configuration failed"
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 4: Testing"
    if curl -s http://localhost/health > /dev/null 2>&1; then
        echo "✅ Application is working"
    else
        echo "❌ Application test failed"
    fi
    
    echo ""
    echo "📊 Status:"
    echo "Flask: $(pgrep -f 'pesticide_search.py' > /dev/null && echo 'running' || echo 'not running')"
    echo "Nginx: $(sudo systemctl is-active nginx)"
    echo "Port 5001: $(sudo netstat -tlnp | grep :5001 > /dev/null && echo 'listening' || echo 'not listening')"
EOF

echo ""
echo "🎉 Quick Fix Applied!"
echo ""
echo "🌐 Test your application:"
echo "   http://$EC2_IP"
echo "   http://$EC2_IP/health"
echo ""
echo "⚠️  This is a temporary fix. For a permanent solution, run:"
echo "   ./deploy_stable_solution.sh"
echo ""
echo "📋 Monitor the application:"
echo "   ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'"

