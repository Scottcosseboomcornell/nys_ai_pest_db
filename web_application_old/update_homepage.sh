#!/bin/bash

# Update Homepage Script
# This script updates the existing live site with the new homepage and routing

echo "🚀 Updating Homepage on Live Site"
echo "================================="

# Configuration - UPDATE THESE VALUES
EC2_IP="3.144.200.224"  # Your actual EC2 IP
EC2_USER="ubuntu"
KEY_PATH="./pesticide-search-key-new.pem"

echo "⚠️  Please update the script with your actual EC2 IP and key path"
echo "Current values:"
echo "  EC2 IP: $EC2_IP"
echo "  Key: $KEY_PATH"
echo ""

# Check if key file exists
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key file not found at $KEY_PATH"
    echo "Please update the KEY_PATH variable in this script"
    exit 1
fi

# Set proper permissions on key
echo "🔐 Setting SSH key permissions..."
chmod 400 "$KEY_PATH"

# Test SSH connection
echo "🔍 Testing SSH connection..."
if ! ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "❌ Error: Cannot connect to EC2 instance"
    echo "Please check:"
    echo "1. EC2 instance is running"
    echo "2. Security group allows SSH (port 22)"
    echo "3. SSH key is correct"
    echo "4. EC2_IP is correct"
    exit 1
fi

echo "✅ SSH connection successful!"

# Copy updated files
echo "📦 Copying updated files..."
scp -i "$KEY_PATH" pesticide_search.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
scp -r -i "$KEY_PATH" templates/ "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"

# Restart the application
echo "🔧 Restarting application..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    cd /home/ubuntu/pesticide-search
    
    # Stop the current application
    echo "🛑 Stopping current application..."
    pkill -f pesticide_search.py
    
    # Wait a moment
    sleep 2
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Start the updated application
    echo "🚀 Starting updated application..."
    nohup python pesticide_search.py > app.log 2>&1 &
    
    # Wait for app to start
    sleep 5
    
    # Check if app is running
    if pgrep -f "pesticide_search.py" > /dev/null; then
        echo "✅ Application updated and started successfully!"
        echo "📊 Recent logs:"
        tail -5 app.log
    else
        echo "❌ Error: Application failed to start"
        echo "📋 Full logs:"
        cat app.log
        exit 1
    fi
EOF

echo ""
echo "🎉 Homepage update completed!"
echo ""
echo "🌐 Your updated website should now be available at:"
echo "   https://cosseboomlab.com"
echo "   https://cosseboomlab.com/pesticide-database"
echo ""
echo "📊 To check the application status:"
echo "   ssh -i $KEY_PATH ubuntu@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'" 