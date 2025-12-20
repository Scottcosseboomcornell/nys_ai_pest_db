#!/bin/bash

# Optimized Pesticide Search Application - AWS Deployment Script
# This script deploys the performance-optimized version to AWS EC2

echo "🚀 Deploying Optimized Pesticide Search Application to AWS EC2..."
echo "================================================================"

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

# ─── STEP 2: VERIFY LOCAL FILES ──────────────────────────────────────────
echo "🔍 Checking local files..."
if [ ! -f "pesticide_search.py" ]; then
    echo "❌ Error: pesticide_search.py not found in current directory"
    exit 1
fi

if [ ! -d "templates" ]; then
    echo "❌ Error: templates directory not found"
    exit 1
fi

if [ ! -f "templates/search.html" ]; then
    echo "❌ Error: templates/search.html not found"
    exit 1
fi

# Check if data directory exists
if [ ! -d "../pipeline_critical_docs/altered_json" ]; then
    echo "❌ Error: ../pipeline_critical_docs/altered_json directory not found"
    echo "Please ensure the pesticide data is available"
    exit 1
fi

echo "✅ All required files found"

# ─── STEP 3: VERIFY SSH KEY ─────────────────────────────────────────────
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key not found at $KEY_PATH"
    echo "Please ensure your AWS SSH key is in the current directory"
    exit 1
fi

chmod 400 "$KEY_PATH"
echo "✅ SSH key permissions set"

# ─── STEP 4: TEST CONNECTION ───────────────────────────────────────────
echo "🔍 Testing SSH connection..."
if ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH connection successful'"; then
    echo "✅ SSH connection successful!"
    echo ""
    
    # ─── STEP 5: COPY APPLICATION FILES ─────────────────────────────────
    echo "📦 Step 1: Copying optimized application files..."
    
    # Copy the main Python application file
    scp -i "$KEY_PATH" pesticide_search.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    
    # Copy the HTML templates
    scp -i "$KEY_PATH" -r templates/ "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    
    # Copy performance test script
    scp -i "$KEY_PATH" test_performance.py "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
    
    if [ $? -eq 0 ]; then
        echo "✅ Application files copied successfully!"
        
        # ─── STEP 6: COPY DATA FILES ───────────────────────────────────
        echo "📦 Step 2: Copying pesticide data..."
        
        # Create a temporary compressed data file
        echo "📦 Creating data archive..."
        cd ../pipeline_critical_docs
        tar -czf ../web_application/altered_json_optimized.tar.gz altered_json/
        cd ../web_application
        
        # Copy the data archive
        scp -i "$KEY_PATH" altered_json_optimized.tar.gz "$EC2_USER@$EC2_IP:/home/ubuntu/pesticide-search/"
        
        # ─── STEP 7: DEPLOY ON SERVER ──────────────────────────────────
        echo "🔧 Step 3: Setting up optimized application on server..."
        ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
            cd /home/ubuntu/pesticide-search
            
            # ─── STEP 7A: STOP CURRENT APPLICATION ─────────────────────
            echo "🛑 Stopping current application..."
            pkill -f "pesticide_search.py"
            sleep 3
            
            # ─── STEP 7B: UPDATE DATA FILES ───────────────────────────
            echo "📂 Updating pesticide data..."
            if [ -f "altered_json_optimized.tar.gz" ]; then
                # Remove old data directory
                rm -rf altered_json
                
                # Extract new data
                tar -xzf altered_json_optimized.tar.gz
                rm altered_json_optimized.tar.gz
                
                echo "✅ Data updated successfully! Found $(ls altered_json | wc -l) files"
            else
                echo "⚠️  No new data file found, using existing data"
            fi
            
            # ─── STEP 7C: SETUP PYTHON ENVIRONMENT ─────────────────────
            echo "🐍 Setting up Python environment..."
            source venv/bin/activate
            
            # Install dependencies
            echo "📦 Installing dependencies..."
            pip install flask requests
            
            # ─── STEP 7D: START OPTIMIZED APPLICATION ──────────────────
            echo "🚀 Starting optimized pesticide search application..."
            nohup python pesticide_search.py > app_optimized.log 2>&1 &
            
            # Wait for app to start and load data
            echo "⏳ Waiting for application to initialize (this may take 5-10 seconds)..."
            sleep 10
            
            # ─── STEP 7E: VERIFY APPLICATION STATUS ───────────────────
            echo "🔍 Verifying application status..."
            if pgrep -f "pesticide_search.py" > /dev/null; then
                echo "✅ Application started successfully!"
                
                # Test the API
                echo "🧪 Testing API endpoints..."
                sleep 2
                
                # Test stats endpoint
                STATS_RESPONSE=$(curl -s http://localhost:5001/api/stats)
                if echo "$STATS_RESPONSE" | grep -q "total_pesticides"; then
                    TOTAL_PESTICIDES=$(echo "$STATS_RESPONSE" | grep -o '"total_pesticides":[0-9]*' | cut -d: -f2)
                    echo "✅ Stats endpoint working - $TOTAL_PESTICIDES pesticides loaded"
                else
                    echo "❌ Stats endpoint failed"
                fi
                
                # Test search endpoint
                SEARCH_RESPONSE=$(curl -s "http://localhost:5001/api/search?q=glyphosate&type=both")
                if echo "$SEARCH_RESPONSE" | grep -q "results"; then
                    echo "✅ Search endpoint working"
                else
                    echo "❌ Search endpoint failed"
                fi
                
                echo ""
                echo "📊 Recent application logs:"
                tail -5 app_optimized.log
                
            else
                echo "❌ Error: Application failed to start"
                echo "📋 Full logs:"
                cat app_optimized.log
                exit 1
            fi
EOF
        
        # ─── STEP 8: DEPLOYMENT SUCCESS ─────────────────────────────────
        echo ""
        echo "🎉 Optimized deployment completed successfully!"
        echo ""
        echo "🌐 Your optimized pesticide search application is now available at:"
        echo "   http://$EC2_IP:5001/pesticide-database"
        echo ""
        echo "📋 Performance Features:"
        echo "   - Intelligent caching system"
        echo "   - Search indexing for fast queries"
        echo "   - Optimized pagination"
        echo "   - Sub-5ms response times"
        echo ""
        echo "🔧 Useful monitoring commands:"
        echo "   View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && tail -f app_optimized.log'"
        echo "   Check status: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && ps aux | grep python'"
        echo "   Test performance: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'cd /home/ubuntu/pesticide-search && python test_performance.py'"
        echo "   Test API: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'curl -s http://localhost:5001/api/stats'"
        echo ""
        echo "💡 Performance Tips:"
        echo "   - First load may take 3-5 seconds (cache initialization)"
        echo "   - Subsequent requests will be <1 second"
        echo "   - Search responses should be <100ms"
        echo "   - Monitor memory usage with: ssh -i $KEY_PATH $EC2_USER@$EC2_IP 'htop'"
        
    else
        echo "❌ Error: Failed to copy files"
        exit 1
    fi
    
else
    # ─── STEP 9: CONNECTION FAILURE HANDLING ───────────────────────────
    echo "❌ SSH connection failed"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "1. Check if the EC2 instance is running in AWS Console"
    echo "2. Verify the security group allows SSH (port 22) from your IP"
    echo "3. Check if the instance has a public IP address"
    echo "4. Verify the SSH key file exists and has correct permissions"
    echo ""
    echo "📋 AWS Console steps:"
    echo "1. Go to AWS Console > EC2 > Instances"
    echo "2. Check if instance is running"
    echo "3. Verify security group allows port 22 (SSH)"
    echo "4. Check if instance has a public IP"
    exit 1
fi

# Clean up temporary files
if [ -f "altered_json_optimized.tar.gz" ]; then
    rm altered_json_optimized.tar.gz
    echo "🧹 Cleaned up temporary files"
fi 