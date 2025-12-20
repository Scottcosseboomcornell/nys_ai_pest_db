#!/bin/bash

# Complete Update Deployment Script
# This script updates templates, Python files, and ensures data is extracted and deployed to AWS

echo "🚀 Complete Update Deployment to AWS EC2..."

# ─── STEP 1: CONFIGURATION SETUP ─────────────────────────────────────────
# Configuration for AWS EC2 instance
EC2_IP="3.144.200.224"  # Public IP address of the EC2 instance
EC2_USER="ubuntu"       # Username for SSH connection
KEY_PATH="pesticide-search-key-new.pem"  # SSH private key file

echo "📋 Configuration:"
echo "   EC2 IP: $EC2_IP"
echo "   User: $EC2_USER"
echo "   Key: $KEY_PATH"
echo ""

# ─── STEP 2: VERIFY SSH KEY ─────────────────────────────────────────────
# Check if SSH key exists (required for secure connection to AWS)
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key not found at $KEY_PATH"
    exit 1
fi

# Set proper permissions on key (SSH requires strict permissions)
chmod 400 "$KEY_PATH"

# ─── STEP 3: TEST CONNECTION ───────────────────────────────────────────
echo "🔍 Testing SSH connection..."
if ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "✅ SSH connection successful!"
    echo ""
    
    # ─── STEP 4: COPY APPLICATION FILES ─────────────────────────────────
    echo "📦 Step 1: Copying updated files..."
    # Copy the unified Python application file
    scp -i "$KEY_PATH" pesticide_search.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    # Copy the pest category lookup module
    scp -i "$KEY_PATH" pest_category_lookup.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    # Copy the target lookup module
    scp -i "$KEY_PATH" target_lookup.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    # Copy the precompute script and precomputed index if present
    scp -i "$KEY_PATH" precompute_filter_index.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    if [ -f precomputed_filter_index.json ]; then
        scp -i "$KEY_PATH" precomputed_filter_index.json "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    fi
    # Copy the precompute crops stats script and precomputed stats if present
    scp -i "$KEY_PATH" precompute_crops_stats.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    if [ -f precomputed_crops_stats.json ]; then
        scp -i "$KEY_PATH" precomputed_crops_stats.json "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    fi
    # Copy the HTML templates (web interface files)
    scp -i "$KEY_PATH" -r templates/ "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    # Copy the docs directory (for downloadable files)
    scp -i "$KEY_PATH" -r docs/ "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    
    if [ $? -eq 0 ]; then
        echo "✅ Files copied successfully!"
        
        # ─── STEP 5: COPY DATA FILES ───────────────────────────────────
        echo "📦 Step 2: Copying data file (if needed)..."
        # Copy the compressed data archive to the server
        scp -i "$KEY_PATH" altered_json.tar.gz "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
        
        # ─── STEP 6: DEPLOY ON SERVER ──────────────────────────────────
        echo "🔧 Step 3: Setting up application and data..."
        ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
            cd /home/ubuntu/pesticide-search
            
            # ─── STEP 6A: STOP CURRENT APPLICATION ─────────────────────
            # Stop the current application to prevent conflicts
            pkill -f "pesticide_search.py" || true
            sleep 2  # Wait for process to fully stop
            
            # ─── STEP 6B: EXTRACT DATA FILES ───────────────────────────
            # Always extract new data when archive is provided to ensure updates
            if [ -f "altered_json.tar.gz" ]; then
                echo "📂 Extracting updated altered_json.tar.gz..."
                # Remove old data to ensure clean update
                rm -rf altered_json
                tar -xzf altered_json.tar.gz  # Extract the compressed data
                if [ -d "altered_json" ] && [ "$(ls -A altered_json)" ]; then
                    echo "✅ Data updated successfully! Found $(ls altered_json | wc -l) files"
                    rm altered_json.tar.gz  # Clean up the compressed file
                else
                    echo "❌ Error: Data extraction failed"
                    exit 1
                fi
            else
                echo "⚠️  No new data archive found, keeping existing data"
            fi
            
            # ─── STEP 6C: SETUP PYTHON ENVIRONMENT ─────────────────────
            # Activate virtual environment (isolated Python environment)
            source venv/bin/activate
            
            # Install any missing dependencies
            echo "📦 Installing dependencies..."
            pip install flask openpyxl  # Install Flask web framework and Excel support
            
            # ─── STEP 6D: START APPLICATION ───────────────────────────
            # Start the application in the background
            echo "🚀 Starting pesticide search application..."
            nohup python pesticide_search.py > app.log 2>&1 &
            
            # Wait for app to start (give it time to initialize)
            sleep 5
            
            # ─── STEP 6E: VERIFY APPLICATION STATUS ───────────────────
            # Check if app is running successfully
            if pgrep -f "pesticide_search.py" > /dev/null; then
                echo "✅ Application started successfully!"
                echo "📊 Recent logs:"
                tail -10 app.log  # Show recent log entries
            else
                echo "❌ Error: Application failed to start"
                echo "📋 Full logs:"
                cat app.log  # Show full logs for debugging
                exit 1
            fi
EOF
        
        # ─── STEP 7: DEPLOYMENT SUCCESS ─────────────────────────────────
        echo ""
        echo "🎉 Complete update deployment finished!"
        echo ""
        echo "🌐 Your updated pesticide search frontend is now available at:"
        echo "   http://$EC2_IP:5000/pesticide-database"
        echo ""
        echo "📋 Useful monitoring commands:"
        echo "   View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'"
        echo "   Check status: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && ps aux | grep python'"
        echo "   Test API: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'curl -s http://localhost:5000/api/pesticides?page=1&per_page=5 | head -10'"
        
    else
        echo "❌ Error: Failed to copy files"
        exit 1
    fi
    
else
    # ─── STEP 8: CONNECTION FAILURE HANDLING ───────────────────────────
    echo "❌ SSH connection failed"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "1. Check if the EC2 instance is running in AWS Console"
    echo "2. Verify the security group allows SSH (port 22) from your IP"
    echo "3. Check if the instance has a public IP address"
    exit 1
fi 