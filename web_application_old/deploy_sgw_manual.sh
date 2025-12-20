#!/bin/bash

# Manual SGW Deployment Script
# Use this script when SSH access is restored

echo "🚀 Manual SGW Landing Page Deployment"
echo "======================================"
echo ""
echo "This script will help you deploy the SGW landing page to cosseboomlab.com/sgw"
echo "once SSH access to your EC2 instance is restored."
echo ""

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="pesticide-search-key-new.pem"

echo "📋 Configuration:"
echo "   EC2 IP: $EC2_IP"
echo "   User: $EC2_USER"
echo "   Key: $KEY_PATH"
echo ""

# Check if key exists
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key not found at $KEY_PATH"
    echo "Please make sure the key file is in the current directory."
    exit 1
fi

echo "🔍 Testing SSH connection..."
if ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "✅ SSH connection successful!"
    echo ""
    
    echo "📦 Step 1: Creating application directory..."
    ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" "mkdir -p /home/ubuntu/pesticide-search"
    
    echo "📦 Step 2: Copying SGW landing page..."
    scp -i "$KEY_PATH" sgw_landing_page.html "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    
    echo "🔧 Step 3: Setting up Flask application..."
    ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
        cd /home/ubuntu/pesticide-search
        
        # Create templates directory
        mkdir -p templates
        
        # Move SGW page to templates
        mv sgw_landing_page.html templates/sgw.html
        
        # Create basic Flask app if it doesn't exist
        if [ ! -f "pesticide_search.py" ]; then
            cat > pesticide_search.py << 'PYTHON_EOF'
from flask import Flask, render_template
import os

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sgw")
def sgw():
    return render_template("sgw.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
PYTHON_EOF
        else
            # Add SGW route to existing app if not present
            if ! grep -q "sgw" pesticide_search.py; then
                echo "Adding SGW route to existing Flask app..."
                # Create backup
                cp pesticide_search.py pesticide_search.py.backup
                # Add route before main route
                sed -i '/@app.route("\/")/i @app.route("/sgw")\ndef sgw():\n    return render_template("sgw.html")\n' pesticide_search.py
            fi
        fi
        
        # Create requirements.txt if it doesn't exist
        if [ ! -f "requirements.txt" ]; then
            echo "Flask==2.3.3" > requirements.txt
        fi
        
        # Set up virtual environment
        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        
        # Activate venv and install dependencies
        source venv/bin/activate
        pip install -r requirements.txt
        
        # Start the application
        echo "🚀 Starting Flask application..."
        nohup python pesticide_search.py > app.log 2>&1 &
        
        # Wait for app to start
        sleep 3
        
        # Check if app is running
        if pgrep -f "pesticide_search.py" > /dev/null; then
            echo "✅ Application started successfully!"
            echo "📊 Recent logs:"
            tail -5 app.log
        else
            echo "❌ Application failed to start"
            echo "📋 Full logs:"
            cat app.log
        fi
EOF
    
    echo ""
    echo "🎉 Deployment completed!"
    echo ""
    echo "🌐 Your SGW page should now be available at:"
    echo "   http://cosseboomlab.com/sgw"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'"
    echo "   Stop app: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && pkill -f pesticide_search.py'"
    echo "   Check status: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && ps aux | grep python'"
    
else
    echo "❌ SSH connection failed"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "1. Check if the EC2 instance is running in AWS Console"
    echo "2. Verify the security group allows SSH (port 22) from your IP"
    echo "3. Try connecting via AWS Systems Manager Session Manager"
    echo "4. Check if the instance has a public IP address"
    echo ""
    echo "📋 AWS CLI commands to check instance status:"
    echo "   aws ec2 describe-instances --instance-ids i-0f842f7f154dfda2d"
    echo "   aws ec2 describe-instance-status --instance-ids i-0f842f7f154dfda2d"
    echo ""
    echo "🔄 Once SSH access is restored, run this script again."
fi 