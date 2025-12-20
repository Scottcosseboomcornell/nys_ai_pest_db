#!/bin/bash

# Quick Deployment Script for New EC2 Instance
# This script assumes you have a new EC2 instance with a working SSH key

echo "🚀 Quick Deployment for New EC2 Instance"
echo "========================================"

# Configuration - UPDATE THESE VALUES
NEW_EC2_IP="3.144.200.224"
NEW_KEY_PATH="/Users/sdc99/Library/CloudStorage/OneDrive-SharedLibraries-CornellUniversity/HVL Plant Path Lab - Documents/AI Pesticide Database/PesticidedatabaseteamUMD_Final/FinalDeliverable/Integration/pesticide-search-key-new.pem"

echo "⚠️  Please update the script with your new EC2 IP and key path"
echo "Current values:"
echo "  EC2 IP: $NEW_EC2_IP"
echo "  Key: $NEW_KEY_PATH"
echo ""

# Check if values are set
if [ "$NEW_EC2_IP" = "YOUR_NEW_EC2_IP_HERE" ] || [ "$NEW_KEY_PATH" = "YOUR_NEW_KEY_PATH.pem" ]; then
    echo "❌ Please update the script with your actual values first!"
    echo ""
    echo "Steps to get new instance:"
    echo "1. Go to AWS Console → EC2 → Launch Instance"
    echo "2. Choose Ubuntu 22.04 LTS"
    echo "3. Instance type: t2.micro"
    echo "4. Create new key pair"
    echo "5. Security group: Allow SSH (22), HTTP (80), Custom TCP (5000)"
    echo "6. Launch instance"
    echo "7. Update this script with the new IP and key path"
    exit 1
fi

# Test connection
echo "🔍 Testing connection to new instance..."
if ssh -i "$NEW_KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@"$NEW_EC2_IP" "echo 'Connection successful'"; then
    echo "✅ Connection successful!"
else
    echo "❌ Connection failed"
    exit 1
fi

# Copy files
echo "📦 Copying files to new instance..."
scp -i "$NEW_KEY_PATH" output_json.tar.gz ubuntu@"$NEW_EC2_IP":/home/ubuntu/
scp -i "$NEW_KEY_PATH" pesticide_search.py ubuntu@"$NEW_EC2_IP":/home/ubuntu/
scp -r -i "$NEW_KEY_PATH" templates/ ubuntu@"$NEW_EC2_IP":/home/ubuntu/

# Setup and start application
echo "🔧 Setting up application on new instance..."
ssh -i "$NEW_KEY_PATH" ubuntu@"$NEW_EC2_IP" << 'EOF'
    # Update system
    sudo apt update
    
    # Install Python and dependencies
    sudo apt install -y python3 python3-pip python3-venv
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install Flask
    pip install flask
    
    # Extract data
    tar -xzf output_json.tar.gz
    rm output_json.tar.gz
    
    # Start application
    nohup python pesticide_search.py > app.log 2>&1 &
    
    # Wait for app to start
    sleep 5
    
    # Check if running
    if pgrep -f "pesticide_search.py" > /dev/null; then
        echo "✅ Application started successfully!"
        echo "🌐 Access at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):5000"
    else
        echo "❌ Application failed to start"
        cat app.log
    fi
EOF

echo ""
echo "🎉 Deployment completed!"
echo "🌐 Your pesticide search frontend should be available at:"
echo "   http://$NEW_EC2_IP:5000" 