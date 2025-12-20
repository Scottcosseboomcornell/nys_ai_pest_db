#!/bin/bash

# Update Templates Deployment Script
# This script updates the templates on the AWS EC2 instance

echo "🚀 Updating templates on AWS EC2..."

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
    exit 1
fi

# Set proper permissions on key
chmod 400 "$KEY_PATH"

echo "🔍 Testing SSH connection..."
if ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "✅ SSH connection successful!"
    echo ""
    
    echo "📦 Copying updated templates..."
    scp -i "$KEY_PATH" -r templates/ "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    
    if [ $? -eq 0 ]; then
        echo "✅ Templates copied successfully!"
        
        echo "🔄 Restarting application..."
        ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
            cd /home/ubuntu/pesticide-search
            
            # Stop the current application
            pkill -f "pesticide_search.py"
            
            # Wait a moment
            sleep 2
            
            # Start the application again
            source venv/bin/activate
            nohup python pesticide_search.py > app.log 2>&1 &
            
            # Wait for app to start
            sleep 3
            
            # Check if app is running
            if pgrep -f "pesticide_search.py" > /dev/null; then
                echo "✅ Application restarted successfully!"
                echo "📊 Recent logs:"
                tail -5 app.log
            else
                echo "❌ Application failed to restart"
                echo "📋 Full logs:"
                cat app.log
            fi
EOF
        
        echo ""
        echo "🎉 Template update completed!"
        echo ""
        echo "🌐 Your updated pesticide search frontend is now available at:"
        echo "   http://$EC2_IP:5000/pesticide-database"
        echo ""
        echo "📋 Useful commands:"
        echo "   View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app.log'"
        echo "   Check status: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && ps aux | grep python'"
        
    else
        echo "❌ Error: Failed to copy templates"
        exit 1
    fi
    
else
    echo "❌ SSH connection failed"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "1. Check if the EC2 instance is running in AWS Console"
    echo "2. Verify the security group allows SSH (port 22) from your IP"
    echo "3. Check if the instance has a public IP address"
    exit 1
fi 