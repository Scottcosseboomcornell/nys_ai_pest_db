#!/bin/bash

# Diagnose 502 Bad Gateway Error Script
# This script checks nginx configuration and Flask app status

echo "🔍 Diagnosing 502 Bad Gateway Error"
echo "==================================="

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="$1"  # Pass the key path as first argument

# Check if key path is provided
if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./diagnose_502_error.sh /path/to/your/pesticide-search-key-new.pem"
    exit 1
fi

# Check if key file exists
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key file not found at $KEY_PATH"
    exit 1
fi

# Set proper permissions on key
chmod 400 "$KEY_PATH"

# Test SSH connection
echo "🔍 Testing SSH connection..."
if ! ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "❌ Error: Cannot connect to EC2 instance"
    exit 1
fi

echo "✅ SSH connection successful!"

# Diagnose the issue
echo "🔍 Diagnosing 502 Bad Gateway issue..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    echo "📊 System Status Check"
    echo "====================="
    
    # Check nginx status
    echo ""
    echo "🌐 Nginx Status:"
    sudo systemctl status nginx --no-pager -l
    
    # Check nginx configuration
    echo ""
    echo "⚙️  Nginx Configuration:"
    sudo nginx -t
    echo ""
    echo "Nginx sites configuration:"
    sudo cat /etc/nginx/sites-available/default | grep -A 10 -B 5 "proxy_pass\|location"
    
    # Check what's listening on ports
    echo ""
    echo "🔍 Port Status:"
    echo "Port 80 (HTTP):"
    sudo netstat -tlnp | grep :80 || echo "Port 80 not listening"
    echo ""
    echo "Port 5000:"
    sudo netstat -tlnp | grep :5000 || echo "Port 5000 not listening"
    echo ""
    echo "Port 5001:"
    sudo netstat -tlnp | grep :5001 || echo "Port 5001 not listening"
    
    # Check Python processes
    echo ""
    echo "🐍 Python Processes:"
    ps aux | grep python | grep -v grep || echo "No Python processes running"
    
    # Check application directory
    echo ""
    echo "📁 Application Directory:"
    if [ -d "/home/ubuntu/pesticide-search" ]; then
        cd /home/ubuntu/pesticide-search
        echo "✅ Application directory exists"
        echo "Contents:"
        ls -la
        
        # Check if Flask app is running
        echo ""
        echo "🔍 Flask Application Status:"
        if pgrep -f "pesticide_search.py" > /dev/null; then
            echo "✅ Flask app is running"
            echo "Process details:"
            ps aux | grep pesticide_search.py | grep -v grep
        else
            echo "❌ Flask app is NOT running"
        fi
        
        # Check application logs
        echo ""
        echo "📋 Application Logs:"
        if [ -f "app.log" ]; then
            echo "Recent log entries:"
            tail -20 app.log
        else
            echo "No app.log found"
        fi
        
        # Test local Flask connection
        echo ""
        echo "🧪 Testing Local Flask Connection:"
        if curl -s http://localhost:5001/api/stats > /dev/null 2>&1; then
            echo "✅ Flask app responds on port 5001"
        elif curl -s http://localhost:5000/api/stats > /dev/null 2>&1; then
            echo "✅ Flask app responds on port 5000"
        else
            echo "❌ Flask app not responding on either port"
        fi
        
    else
        echo "❌ Application directory not found"
    fi
    
    # Check system resources
    echo ""
    echo "💾 System Resources:"
    echo "Memory usage:"
    free -h
    echo ""
    echo "Disk usage:"
    df -h /
    echo ""
    echo "Load average:"
    uptime
EOF

echo ""
echo "🎯 Common 502 Bad Gateway Causes:"
echo "1. Flask app not running"
echo "2. Flask app running on wrong port (5000 vs 5001)"
echo "3. Nginx proxy_pass pointing to wrong port"
echo "4. Flask app crashed or failed to start"
echo "5. Insufficient memory (t2.micro has only 1GB RAM)"
echo ""
echo "📋 Next steps will be provided based on the diagnosis above."


