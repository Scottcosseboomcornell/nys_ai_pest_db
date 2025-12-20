#!/bin/bash

# Auto Deploy Script - Waits for server and deploys stable solution
# Run this from the Integration directory

echo "🚀 Auto Deploy - Waiting for Server and Deploying Stable Solution"
echo "================================================================"

# Configuration
EC2_IP="3.144.200.224"
KEY_PATH="web_application/pesticide-search-key-new.pem"

echo "📋 Configuration:"
echo "   EC2 IP: $EC2_IP"
echo "   Key: $KEY_PATH"
echo ""

# Check if we're in the right directory
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key not found at $KEY_PATH"
    echo "Please run this script from the Integration directory"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo "🔄 Step 1: Waiting for server to come online..."
echo "Press Ctrl+C to stop waiting"
echo ""

# Wait for server to come online
while true; do
    # Test ping
    if ping -c 1 -W 3 "$EC2_IP" > /dev/null 2>&1; then
        echo "✅ $(date): Server is responding to ping"
        
        # Test SSH
        if ssh -i "$KEY_PATH" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "ubuntu@$EC2_IP" "echo 'SSH test'" > /dev/null 2>&1; then
            echo "✅ $(date): SSH connection successful"
            break
        else
            echo "⚠️  $(date): Ping works but SSH not responding yet"
        fi
    else
        echo "❌ $(date): Server not responding to ping"
    fi
    
    sleep 10
done

echo ""
echo "🎉 Server is online! Starting deployment..."
echo ""

# Run the stable deployment
echo "🔄 Step 2: Deploying stable solution..."
./web_application/deploy_stable_solution.sh

echo ""
echo "🎉 Auto deployment completed!"
echo ""
echo "🌐 Test your website:"
echo "   http://$EC2_IP"
echo "   http://$EC2_IP/api/stats"
echo ""
echo "📋 Monitor the application:"
echo "   ssh -i $KEY_PATH ubuntu@$EC2_IP 'sudo systemctl status pesticide-search'"



