# SSL Certificate Renewal Guide for cosseboomlab.com

## 🎯 **Goal**
Restore HTTPS access to your pesticide database website by renewing SSL certificates.

## 🔧 **Step 1: Access Your Server**

### **Option A: AWS Console (Recommended)**
1. Go to [AWS Console](https://console.aws.amazon.com/ec2/)
2. Navigate to **EC2 → Instances**
3. Find instance: `i-0f842f7f154dfda2d (pesticide-search-fresh)`
4. Click **"Connect"** button
5. Choose **"EC2 Instance Connect"** (browser-based SSH)
6. Click **"Connect"**

### **Option B: SSH from Terminal**
If you have the SSH key file:
```bash
ssh -i /path/to/pesticide-search-key-new.pem ubuntu@3.144.200.224
```

### **Option C: Alternative SSH Methods**
If standard SSH fails, try:
```bash
# With different timeout settings
ssh -i /path/to/pesticide-search-key-new.pem -o ConnectTimeout=60 -o ServerAliveInterval=30 ubuntu@3.144.200.224

# With verbose output to see what's happening
ssh -i /path/to/pesticide-search-key-new.pem -v ubuntu@3.144.200.224
```

## 🔍 **Step 2: Check Current Status**

Once connected to the server, run these commands:

```bash
# Check if certbot is installed
certbot --version

# Check current certificate status
sudo certbot certificates

# Check if certificate files exist
ls -la /etc/letsencrypt/live/cosseboomlab.com/

# Check nginx status
sudo systemctl status nginx

# Check what ports are listening
sudo netstat -tlnp | grep nginx
```

## 🔧 **Step 3: Renew SSL Certificates**

### **Method A: Renew Existing Certificates**
```bash
# Test renewal (dry run)
sudo certbot renew --dry-run

# If test passes, run actual renewal
sudo certbot renew
```

### **Method B: Obtain New Certificates**
If renewal fails, obtain new certificates:

```bash
# Stop nginx temporarily
sudo systemctl stop nginx

# Obtain new certificates
sudo certbot certonly --standalone \
  -d cosseboomlab.com \
  -d www.cosseboomlab.com \
  --non-interactive \
  --agree-tos \
  --email admin@cosseboomlab.com

# Start nginx again
sudo systemctl start nginx
```

### **Method C: Force Renewal**
If certificates are close to expiry:
```bash
sudo certbot renew --force-renewal
```

## ⚙️ **Step 4: Configure Nginx for HTTPS**

Create the HTTPS nginx configuration:

```bash
sudo tee /etc/nginx/sites-available/default > /dev/null << 'EOF'
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
EOF
```

## 🧪 **Step 5: Test and Restart Services**

```bash
# Test nginx configuration
sudo nginx -t

# If test passes, restart nginx
sudo systemctl restart nginx

# Check nginx status
sudo systemctl status nginx

# Check what ports are now listening
sudo netstat -tlnp | grep nginx

# Test HTTPS locally
curl -k https://localhost/health
curl -k https://localhost/api/stats
```

## ✅ **Step 6: Verify HTTPS is Working**

Test from your local machine:

```bash
# Test HTTPS access
curl https://cosseboomlab.com/health
curl https://cosseboomlab.com/api/stats

# Test HTTP redirect
curl -I http://cosseboomlab.com/
# Should show: HTTP/1.1 301 Moved Permanently
# Location: https://cosseboomlab.com/
```

## 🚨 **Troubleshooting**

### **If Certificate Renewal Fails:**

1. **Check domain DNS:**
   ```bash
   nslookup cosseboomlab.com
   # Should return: 3.144.200.224
   ```

2. **Check port 80 accessibility:**
   ```bash
   sudo netstat -tlnp | grep :80
   # Should show nginx listening on port 80
   ```

3. **Check Let's Encrypt rate limits:**
   ```bash
   sudo certbot certificates
   # Look for any error messages
   ```

4. **Manual certificate check:**
   ```bash
   openssl x509 -in /etc/letsencrypt/live/cosseboomlab.com/fullchain.pem -text -noout | grep -E "(Subject:|Not Before|Not After|DNS:)"
   ```

### **If Nginx Configuration Fails:**

1. **Check nginx syntax:**
   ```bash
   sudo nginx -t
   ```

2. **Check nginx error logs:**
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

3. **Restart nginx:**
   ```bash
   sudo systemctl restart nginx
   ```

## 📋 **Expected Results**

After successful completion:

- ✅ **HTTP**: `http://cosseboomlab.com` → redirects to HTTPS
- ✅ **HTTPS**: `https://cosseboomlab.com` → works with SSL
- ✅ **API**: `https://cosseboomlab.com/api/stats` → returns JSON
- ✅ **Health**: `https://cosseboomlab.com/health` → returns "healthy"

## 🔄 **Automatic Renewal Setup**

To prevent this issue in the future, set up automatic renewal:

```bash
# Test automatic renewal
sudo certbot renew --dry-run

# Add to crontab for automatic renewal
sudo crontab -e
# Add this line:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 📞 **If You Need Help**

If you encounter issues:

1. **Check the error messages** in the terminal
2. **Verify domain DNS** is pointing to the correct IP
3. **Ensure port 80** is accessible from the internet
4. **Check Let's Encrypt rate limits** (5 certificates per week per domain)

Your pesticide database is currently working on HTTP, so you can continue using it while fixing HTTPS!

