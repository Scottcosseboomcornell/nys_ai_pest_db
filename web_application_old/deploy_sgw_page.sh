#!/bin/bash

# SGW Landing Page Deployment Script
# This script uploads the SGW landing page to the /sgw route on cosseboomlab.com

set -e  # Exit on any error

echo "🚀 Deploying SGW landing page to cosseboomlab.com/sgw..."

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="$1"  # Pass the key path as first argument

# Check if key path is provided
if [ -z "$KEY_PATH" ]; then
    echo "❌ Error: Please provide the path to your SSH key"
    echo "Usage: ./deploy_sgw_page.sh /path/to/your/pesticide-pipeline-key.pem"
    echo ""
    echo "To get your SSH key:"
    echo "1. Go to AWS Console → EC2 → Key Pairs"
    echo "2. Find 'pesticide-pipeline-key'"
    echo "3. Download the .pem file"
    echo "4. Run: ./deploy_sgw_page.sh ~/Downloads/pesticide-pipeline-key.pem"
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

# Copy the SGW landing page
echo "📦 Copying SGW landing page..."
if scp -i "$KEY_PATH" sgw_landing_page.html "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"; then
    echo "✅ SGW landing page copied successfully!"
else
    echo "❌ Error: Failed to copy SGW landing page"
    exit 1
fi

# Set up the SGW route on the server
echo "🔧 Setting up SGW route on the server..."
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
    cd /home/ubuntu/pesticide-search
    
    # Create templates directory if it doesn't exist
    mkdir -p templates
    
    # Move the SGW page to templates directory
    mv sgw_landing_page.html templates/sgw.html
    
    # Check if the Flask app needs to be updated to include the SGW route
    if ! grep -q "sgw" pesticide_search.py; then
        echo "📝 Adding SGW route to Flask app..."
        
        # Create a backup of the current app
        cp pesticide_search.py pesticide_search.py.backup
        
        # Add the SGW route before the main route
        sed -i '/@app.route("\/")/i @app.route("/sgw")\ndef sgw():\n    return render_template("sgw.html")\n' pesticide_search.py
        
        echo "✅ SGW route added to Flask app"
    else
        echo "✅ SGW route already exists in Flask app"
    fi
    
    # Restart the application
    echo "🔄 Restarting application..."
    pkill -f "pesticide_search.py" || true
    sleep 2
    
    # Activate virtual environment and start app
    source venv/bin/activate
    nohup python pesticide_search.py > app.log 2>&1 &
    
    # Wait a moment for the app to start
    sleep 3
    
    # Check if app is running
    if pgrep -f "pesticide_search.py" > /dev/null; then
        echo "✅ Application restarted successfully!"
        echo "📊 Application logs:"
        tail -5 app.log
    else
        echo "❌ Error: Application failed to restart"
        echo "📋 Full logs:"
        cat app.log
        exit 1
    fi
EOF

echo "🎉 SGW landing page deployment completed!"
echo ""
echo "🌐 Your SGW page is now available at:"
echo "   http://cosseboomlab.com/sgw"
echo ""
echo "📋 Useful commands:"
echo "   View logs: ssh -i $KEY_PATH ubuntu@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'"
echo "   Stop app: ssh -i $KEY_PATH ubuntu@$EC2_IP 'cd /home/ubuntu/pesticide-search && pkill -f pesticide_search.py'"
echo "   Check files: ssh -i $KEY_PATH ubuntu@$EC2_IP 'cd /home/ubuntu/pesticide-search && ls -la templates/'" 