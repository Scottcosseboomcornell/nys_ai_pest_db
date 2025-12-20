#!/bin/bash

# Restore SSL Certificates for cosseboomlab.com
# This script restores or renews Let's Encrypt certificates

echo "🔧 Restoring SSL Certificates for cosseboomlab.com"
echo "================================================="

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="$1"

if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./restore_ssl_certificates.sh /path/to/your/pesticide-search-key-new.pem"
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

# Restore SSL certificates
echo "🔧 Restoring SSL certificates..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    echo "🔍 Step 1: Check Let's Encrypt status"
    echo "===================================="
    
    # Check if certbot is installed
    if command -v certbot > /dev/null; then
        echo "✅ Certbot is installed"
        certbot --version
    else
        echo "❌ Certbot is not installed"
        echo "Installing certbot..."
        sudo apt update
        sudo apt install -y certbot python3-certbot-nginx
    fi
    
    # Check current certificate status
    echo ""
    echo "Current certificate status:"
    sudo certbot certificates 2>/dev/null || echo "No certificates found or certbot error"
    
    echo ""
    echo "🔍 Step 2: Check certificate files"
    echo "================================="
    
    # Check if certificate files exist
    if [ -f "/etc/letsencrypt/live/cosseboomlab.com/fullchain.pem" ]; then
        echo "✅ Certificate files exist"
        echo "Certificate details:"
        openssl x509 -in /etc/letsencrypt/live/cosseboomlab.com/fullchain.pem -text -noout | grep -E "(Subject:|Not Before|Not After|DNS:)"
    else
        echo "❌ Certificate files missing"
        echo "Checking archive directory..."
        if [ -d "/etc/letsencrypt/archive/cosseboomlab.com" ]; then
            echo "✅ Archive directory exists"
            ls -la /etc/letsencrypt/archive/cosseboomlab.com/
        else
            echo "❌ Archive directory missing"
        fi
    fi
    
    echo ""
    echo "🔧 Step 3: Attempt certificate renewal/restoration"
    echo "================================================="
    
    # Try to renew existing certificates
    echo "Attempting certificate renewal..."
    if sudo certbot renew --dry-run 2>/dev/null; then
        echo "✅ Certificate renewal test successful"
        echo "Running actual renewal..."
        sudo certbot renew --quiet
    else
        echo "❌ Certificate renewal failed or no certificates to renew"
        echo "Attempting to obtain new certificates..."
        
        # Stop nginx temporarily for certificate generation
        sudo systemctl stop nginx
        
        # Try to obtain new certificates
        if sudo certbot certonly --standalone -d cosseboomlab.com -d www.cosseboomlab.com --non-interactive --agree-tos --email admin@cosseboomlab.com; then
            echo "✅ New certificates obtained successfully"
        else
            echo "❌ Failed to obtain new certificates"
            echo "This might be due to:"
            echo "1. Domain not pointing to this server"
            echo "2. Port 80 not accessible"
            echo "3. Rate limiting from Let's Encrypt"
        fi
        
        # Start nginx again
        sudo systemctl start nginx
    fi
    
    echo ""
    echo "🔍 Step 4: Verify certificates"
    echo "============================="
    
    # Check if certificates are now available
    if [ -f "/etc/letsencrypt/live/cosseboomlab.com/fullchain.pem" ]; then
        echo "✅ Certificates are now available"
        echo "Certificate details:"
        openssl x509 -in /etc/letsencrypt/live/cosseboomlab.com/fullchain.pem -text -noout | grep -E "(Subject:|Not Before|Not After|DNS:)"
        
        # Update nginx configuration for HTTPS
        echo ""
        echo "🔧 Step 5: Update nginx for HTTPS"
        echo "================================"
        
        # Create HTTPS-enabled nginx configuration
        sudo tee /etc/nginx/sites-available/default > /dev/null << 'NGINX_CONFIG'
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
    ssl_certificate /etc/letsencrypt/live/cosseboomlab.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cosseboomlab.com/privkey.pem;
    
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
        
        # Test and restart nginx
        if sudo nginx -t; then
            echo "✅ HTTPS nginx configuration is valid"
            sudo systemctl restart nginx
            echo "✅ Nginx restarted with HTTPS configuration"
        else
            echo "❌ HTTPS nginx configuration is invalid"
            sudo nginx -t
        fi
        
    else
        echo "❌ Certificates are still not available"
        echo "You may need to:"
        echo "1. Check domain DNS settings"
        echo "2. Ensure port 80 is accessible"
        echo "3. Wait for Let's Encrypt rate limits to reset"
    fi
    
    echo ""
    echo "📊 Final Status:"
    echo "==============="
    echo "Nginx: $(sudo systemctl is-active nginx)"
    echo "Flask: $(pgrep -f 'pesticide_search.py' > /dev/null && echo 'running' || echo 'not running')"
    
    if [ -f "/etc/letsencrypt/live/cosseboomlab.com/fullchain.pem" ]; then
        echo "SSL: ✅ Enabled with Let's Encrypt certificates"
        echo "Listening ports:"
        netstat -tlnp 2>/dev/null | grep nginx || echo "No nginx ports found"
    else
        echo "SSL: ❌ Disabled (certificates not available)"
    fi
EOF

echo ""
echo "🎉 SSL Certificate Restoration Completed!"
echo ""
echo "🌐 Your application should now be available at:"
echo "   http://cosseboomlab.com (redirects to HTTPS if SSL is enabled)"
echo "   https://cosseboomlab.com (if SSL certificates were restored)"
echo "   http://cosseboomlab.com/pesticide-database"
echo "   http://cosseboomlab.com/api/stats"
echo ""
echo "🧪 Test the setup:"
echo "   curl http://cosseboomlab.com/health"
echo "   curl http://cosseboomlab.com/api/stats"
echo "   curl https://cosseboomlab.com/health (if HTTPS is working)"
echo ""
echo "💡 If HTTPS is still not working, you may need to:"
echo "   1. Check that cosseboomlab.com points to 3.144.200.224"
echo "   2. Ensure port 80 is accessible from the internet"
echo "   3. Wait for Let's Encrypt rate limits to reset"

