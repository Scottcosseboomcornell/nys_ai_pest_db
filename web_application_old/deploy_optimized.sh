#!/bin/bash

# Deploy Optimized Pesticide Search Application
# This script deploys the performance-optimized version of the application

echo "🚀 Deploying Optimized Pesticide Search Application"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "pesticide_search.py" ]; then
    echo "❌ Error: pesticide_search.py not found in current directory"
    echo "Please run this script from the web_application directory"
    exit 1
fi

# Check if altered_json directory exists
if [ ! -d "altered_json" ]; then
    echo "❌ Error: altered_json directory not found"
    echo "Please ensure the pesticide data is available"
    exit 1
fi

# Count JSON files
JSON_COUNT=$(find altered_json -name "*.json" | wc -l)
echo "📊 Found $JSON_COUNT pesticide JSON files"

# Check if templates directory exists
if [ ! -d "templates" ]; then
    echo "❌ Error: templates directory not found"
    echo "Please ensure the HTML templates are available"
    exit 1
fi

# Check if search.html exists
if [ ! -f "templates/search.html" ]; then
    echo "❌ Error: templates/search.html not found"
    echo "Please ensure the optimized search template is available"
    exit 1
fi

echo "✅ All required files found"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

# Check if required Python packages are installed
echo "🔍 Checking Python dependencies..."
python3 -c "import flask, json, os, glob, time, threading, collections" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Some Python packages may be missing"
    echo "Installing required packages..."
    pip3 install flask
fi

# Stop any existing process on port 5001
echo "🛑 Stopping any existing process on port 5001..."
pkill -f "python.*pesticide_search.py" 2>/dev/null || true

# Wait a moment for the process to stop
sleep 2

# Start the optimized application
echo "🚀 Starting optimized pesticide search application..."
echo "📝 Logs will be saved to pesticide_search.log"
echo "🌐 Application will be available at: http://localhost:5001"
echo ""

# Start the application in the background with logging
nohup python3 pesticide_search.py > pesticide_search.log 2>&1 &

# Get the process ID
APP_PID=$!
echo "📋 Application started with PID: $APP_PID"

# Wait a moment for the application to start
echo "⏳ Waiting for application to start..."
sleep 5

# Check if the application is running
if ps -p $APP_PID > /dev/null; then
    echo "✅ Application is running successfully!"
    
    # Test the application
    echo "🧪 Testing application endpoints..."
    
    # Test stats endpoint
    if curl -s http://localhost:5001/api/stats > /dev/null; then
        echo "✅ Stats endpoint is working"
    else
        echo "❌ Stats endpoint failed"
    fi
    
    # Test pesticides endpoint
    if curl -s http://localhost:5001/api/pesticides?page=1&per_page=5 > /dev/null; then
        echo "✅ Pesticides endpoint is working"
    else
        echo "❌ Pesticides endpoint failed"
    fi
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "📋 Application Details:"
    echo "   - URL: http://localhost:5001"
    echo "   - PID: $APP_PID"
    echo "   - Logs: pesticide_search.log"
    echo "   - Data: $JSON_COUNT pesticide records"
    echo ""
    echo "🔧 Useful Commands:"
    echo "   - View logs: tail -f pesticide_search.log"
    echo "   - Stop app: kill $APP_PID"
    echo "   - Test performance: python3 test_performance.py"
    echo "   - Refresh cache: curl http://localhost:5001/api/cache/refresh"
    echo ""
    echo "💡 Performance Tips:"
    echo "   - First load may take 2-5 seconds (cache initialization)"
    echo "   - Subsequent loads will be much faster (<1 second)"
    echo "   - Search responses should be <100ms"
    echo "   - Monitor memory usage with: htop"
    
else
    echo "❌ Application failed to start"
    echo "📋 Check the logs: cat pesticide_search.log"
    exit 1
fi 