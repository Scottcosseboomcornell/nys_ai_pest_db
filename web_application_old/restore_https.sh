#!/bin/bash

# Restore HTTPS Configuration for cosseboomlab.com
# This script checks for existing SSL certificates and restores HTTPS

echo "🔧 Restoring HTTPS Configuration for cosseboomlab.com"
echo "===================================================="

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="$1"

if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./restore_https.sh /path/to/your/pesticide-search-key-new.pem"
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

# Check and restore HTTPS
echo "🔧 Checking and restoring HTTPS configuration..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    echo "🔍 Step 1: Check for existing SSL certificates"
    echo "============================================="
    
    # Check common SSL certificate locations
    echo "Checking for SSL certificates:"
    
    # Let's Encrypt certificates
    if [ -d "/etc/letsencrypt/live/cosseboomlab.com" ]; then
        echo "✅ Found Let's Encrypt certificates for cosseboomlab.com"
        echo "Certificate files:"
        ls -la /etc/letsencrypt/live/cosseboomlab.com/
        SSL_CERT="/etc/letsencrypt/live/cosseboomlab.com/fullchain.pem"
        SSL_KEY="/etc/letsencrypt/live/cosseboomlab.com/privkey.pem"
        SSL_TYPE="letsencrypt"
    elif [ -f "/etc/ssl/certs/cosseboomlab.com.crt" ] && [ -f "/etc/ssl/private/cosseboomlab.com.key" ]; then
        echo "✅ Found custom SSL certificates for cosseboomlab.com"
        SSL_CERT="/etc/ssl/certs/cosseboomlab.com.crt"
        SSL_KEY="/etc/ssl/private/cosseboomlab.com.key"
        SSL_TYPE="custom"
    elif [ -f "/etc/nginx/ssl/cosseboomlab.com.crt" ] && [ -f "/etc/nginx/ssl/cosseboomlab.com.key" ]; then
        echo "✅ Found nginx SSL certificates for cosseboomlab.com"
        SSL_CERT="/etc/nginx/ssl/cosseboomlab.com.crt"
        SSL_KEY="/etc/nginx/ssl/cosseboomlab.com.key"
        SSL_TYPE="nginx"
    else
        echo "❌ No SSL certificates found for cosseboomlab.com"
        echo "Checking all SSL certificate locations:"
        find /etc -name "*cosseboomlab*" -type f 2>/dev/null || echo "No cosseboomlab certificates found"
        find /etc -name "*ssl*" -type d 2>/dev/null | head -5
        SSL_TYPE="none"
    fi
    
    echo ""
    echo "🔍 Step 2: Check current nginx configuration"
    echo "==========================================="
    
    # Check current nginx configuration
    echo "Current nginx sites configuration:"
    sudo cat /etc/nginx/sites-available/default
    
    echo ""
    echo "🔧 Step 3: Create HTTPS-enabled nginx configuration"
    echo "=================================================="
    
    if [ "$SSL_TYPE" != "none" ]; then
        echo "Creating nginx configuration with HTTPS support..."
        
        # Create nginx configuration with HTTPS
        sudo tee /etc/nginx/sites-available/default > /dev/null << NGINX_CONFIG
# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name cosseboomlab.com www.cosseboomlab.com;
    
    # Redirect all HTTP requests to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name cosseboomlab.com www.cosseboomlab.com;
    
    # SSL configuration
    ssl_certificate $SSL_CERT;
    ssl_certificate_key $SSL_KEY;
    
    # SSL security settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
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
        
        echo "✅ HTTPS nginx configuration created with $SSL_TYPE certificates"
        
    else
        echo "Creating HTTP-only nginx configuration (no SSL certificates found)..."
        
        # Create HTTP-only configuration
        sudo tee /etc/nginx/sites-available/default > /dev/null << NGINX_CONFIG
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _ cosseboomlab.com www.cosseboomlab.com;
    
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
}
NGINX_CONFIG
        
        echo "✅ HTTP-only nginx configuration created"
    fi
    
    echo ""
    echo "🔧 Step 4: Test and restart nginx"
    echo "================================"
    
    # Test nginx configuration
    if sudo nginx -t; then
        echo "✅ Nginx configuration is valid"
    else
        echo "❌ Nginx configuration is invalid"
        sudo nginx -t
        exit 1
    fi
    
    # Restart nginx
    sudo systemctl restart nginx
    
    # Check nginx status
    if sudo systemctl is-active --quiet nginx; then
        echo "✅ Nginx restarted successfully"
    else
        echo "❌ Nginx failed to restart"
        sudo systemctl status nginx --no-pager -l
        exit 1
    fi
    
    echo ""
    echo "🔧 Step 5: Verify HTTPS setup"
    echo "============================"
    
    # Check what ports are listening
    echo "Listening ports:"
    netstat -tlnp 2>/dev/null | grep nginx || echo "No nginx ports found"
    
    # Test HTTPS if certificates exist
    if [ "$SSL_TYPE" != "none" ]; then
        echo ""
        echo "Testing HTTPS locally..."
        if curl -k -s https://localhost/health > /dev/null 2>&1; then
            echo "✅ HTTPS working locally"
        else
            echo "❌ HTTPS not working locally"
        fi
    fi
    
    echo ""
    echo "📊 Final Status:"
    echo "==============="
    echo "Nginx: $(sudo systemctl is-active nginx)"
    echo "Flask: $(pgrep -f 'pesticide_search.py' > /dev/null && echo 'running' || echo 'not running')"
    echo "SSL Type: $SSL_TYPE"
    if [ "$SSL_TYPE" != "none" ]; then
        echo "SSL Certificate: $SSL_CERT"
        echo "SSL Key: $SSL_KEY"
    fi
EOF

echo ""
echo "🎉 HTTPS Configuration Restore Completed!"
echo ""
if [ "$SSL_TYPE" != "none" ]; then
    echo "🌐 Your application should now be available at:"
    echo "   https://cosseboomlab.com (HTTPS - redirects from HTTP)"
    echo "   https://cosseboomlab.com/pesticide-database"
    echo "   https://cosseboomlab.com/api/stats"
    echo ""
    echo "🧪 Test HTTPS:"
    echo "   curl -k https://cosseboomlab.com/health"
    echo "   curl -k https://cosseboomlab.com/api/stats"
else
    echo "🌐 Your application is available at:"
    echo "   http://cosseboomlab.com (HTTP only - no SSL certificates found)"
    echo "   http://cosseboomlab.com/pesticide-database"
    echo "   http://cosseboomlab.com/api/stats"
    echo ""
    echo "💡 To enable HTTPS, you need to:"
    echo "   1. Install SSL certificates (Let's Encrypt recommended)"
    echo "   2. Run this script again"
fi

