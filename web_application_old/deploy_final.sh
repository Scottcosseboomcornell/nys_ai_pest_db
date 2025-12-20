#!/bin/bash

# Final Deployment Script for Pesticide Search Frontend
# This script completes the deployment to AWS EC2

set -e  # Exit on any error

echo "🚀 Starting final deployment to AWS EC2..."

# Configuration
EC2_IP="18.188.172.124"
EC2_USER="ubuntu"
KEY_PATH="$1"  # Pass the key path as first argument

# Check if key path is provided
if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./deploy_final.sh /path/to/your/pesticide-pipeline-key.pem"
    echo ""
    echo "To get your SSH key:"
    echo "1. Go to AWS Console → EC2 → Key Pairs"
    echo "2. Find 'pesticide-pipeline-key'"
    echo "3. Download the .pem file"
    echo "4. Run: ./deploy_final.sh ~/Downloads/pesticide-pipeline-key.pem"
    exit 1
fi

# Check if key file exists
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key file not found at $KEY_PATH"
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
    exit 1
fi

echo "✅ SSH connection successful!"

# Copy compressed data file
echo "📦 Copying compressed data file..."
if scp -i "$KEY_PATH" -o ConnectTimeout=30 output_json.tar.gz "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"; then
    echo "✅ Data file copied successfully!"
else
    echo "❌ Error: Failed to copy data file"
    exit 1
fi

# Extract data and start the application
echo "🔧 Extracting data and starting application..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    cd /home/ubuntu/pesticide-search
    
    # Extract the data
    echo "📂 Extracting output_json.tar.gz..."
    tar -xzf output_json.tar.gz
    rm output_json.tar.gz
    
    # Check if data was extracted
    if [ -d "output_json" ] && [ "$(ls -A output_json)" ]; then
        echo "✅ Data extracted successfully! Found $(ls output_json | wc -l) files"
    else
        echo "❌ Error: Data extraction failed or directory is empty"
        exit 1
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install any missing dependencies
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    
    # Start the application
    echo "🚀 Starting pesticide search application..."
    nohup python pesticide_search.py > app.log 2>&1 &
    
    # Wait a moment for the app to start
    sleep 3
    
    # Check if app is running
    if pgrep -f "pesticide_search.py" > /dev/null; then
        echo "✅ Application started successfully!"
        echo "📊 Application logs:"
        tail -10 app.log
    else
        echo "❌ Error: Application failed to start"
        echo "📋 Full logs:"
        cat app.log
        exit 1
    fi
EOF

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "🌐 Your pesticide search frontend is now available at:"
echo "   http://18.188.172.124:5000"
echo ""
echo "📊 To check the application status:"
echo "   ssh -i $KEY_PATH ubuntu@18.188.172.124 'cd /home/ubuntu/pesticide-search && tail -f app.log'"
echo ""
echo "🛑 To stop the application:"
echo "   ssh -i $KEY_PATH ubuntu@18.188.172.124 'cd /home/ubuntu/pesticide-search && pkill -f pesticide_search.py'"
echo ""
echo "📁 To view application files:"
echo "   ssh -i $KEY_PATH ubuntu@18.188.172.124 'cd /home/ubuntu/pesticide-search && ls -la'" 