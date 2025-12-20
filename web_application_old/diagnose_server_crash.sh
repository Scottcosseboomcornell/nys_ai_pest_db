#!/bin/bash

# Server Crash Diagnosis and Recovery Script
# This script helps diagnose why the EC2 instance is completely down

echo "🚨 EC2 Instance Crash Diagnosis"
echo "==============================="

# Configuration
EC2_IP="3.144.200.224"
EC2_USER="ubuntu"
KEY_PATH="web_application/pesticide-search-key-new.pem"

echo "📋 Configuration:"
echo "   EC2 IP: $EC2_IP"
echo "   User: $EC2_USER"
echo "   Key: $KEY_PATH"
echo ""

# Check if key exists
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Error: SSH key not found at $KEY_PATH"
    echo "Please ensure the SSH key is in the correct location"
    exit 1
fi

chmod 400 "$KEY_PATH"

echo "🔍 Step 1: Network Connectivity Tests"
echo "====================================="

# Test basic connectivity
echo "Testing ping connectivity..."
if ping -c 3 -W 5 "$EC2_IP" > /dev/null 2>&1; then
    echo "✅ Ping successful - server is reachable"
else
    echo "❌ Ping failed - server is not responding to ICMP"
    echo "   This could mean:"
    echo "   - Server is completely down"
    echo "   - Security group blocks ICMP"
    echo "   - Network issues"
fi

# Test SSH connectivity
echo ""
echo "Testing SSH connectivity..."
if timeout 30 ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'SSH test successful'" 2>/dev/null; then
    echo "✅ SSH connection successful"
    SSH_WORKING=true
else
    echo "❌ SSH connection failed"
    echo "   This could mean:"
    echo "   - Server is completely down"
    echo "   - SSH service is not running"
    echo "   - Security group blocks SSH (port 22)"
    echo "   - Instance has crashed or stopped"
    SSH_WORKING=false
fi

# Test HTTP connectivity
echo ""
echo "Testing HTTP connectivity..."
if curl -s --connect-timeout 10 --max-time 15 "http://$EC2_IP" > /dev/null 2>&1; then
    echo "✅ HTTP connection successful"
    HTTP_WORKING=true
else
    echo "❌ HTTP connection failed"
    echo "   This could mean:"
    echo "   - Web server is down"
    echo "   - Security group blocks HTTP (port 80)"
    echo "   - Application has crashed"
    HTTP_WORKING=false
fi

echo ""
echo "🔍 Step 2: AWS Console Check Required"
echo "====================================="
echo "Please check your AWS Console for the following:"
echo ""
echo "1. **EC2 Dashboard**:"
echo "   - Go to EC2 Dashboard → Instances"
echo "   - Find your instance (IP: $EC2_IP)"
echo "   - Check the 'State' column:"
echo "     • 'Running' = Instance is up but may have issues"
echo "     • 'Stopped' = Instance was stopped (manually or crashed)"
echo "     • 'Stopping' = Instance is shutting down"
echo "     • 'Pending' = Instance is starting up"
echo ""
echo "2. **Instance Details**:"
echo "   - Click on the instance"
echo "   - Check 'Status Checks' tab:"
echo "     • System Status Check"
echo "     • Instance Status Check"
echo ""
echo "3. **CloudWatch Logs** (if enabled):"
echo "   - Go to CloudWatch → Logs"
echo "   - Look for system logs or application logs"
echo ""
echo "4. **Security Groups**:"
echo "   - Check if security group allows:"
echo "     • SSH (port 22) from your IP"
echo "     • HTTP (port 80) from anywhere (0.0.0.0/0)"
echo "     • HTTPS (port 443) from anywhere (0.0.0.0/0)"

echo ""
echo "🔍 Step 3: Common Crash Causes"
echo "=============================="
echo "Based on the symptoms, here are the most likely causes:"
echo ""
echo "1. **Out of Memory (OOM) Kill**:"
echo "   - t2.micro has only 1GB RAM"
echo "   - Loading 15,000+ JSON files can cause OOM"
echo "   - System kills the process or crashes the instance"
echo ""
echo "2. **Instance Stop/Restart**:"
echo "   - AWS may have stopped the instance"
echo "   - Scheduled maintenance"
echo "   - Billing issues"
echo ""
echo "3. **Application Crash**:"
echo "   - Flask app crashed and took down the system"
echo "   - Memory leak or infinite loop"
echo "   - File system corruption"
echo ""
echo "4. **Network Issues**:"
echo "   - Security group changes"
echo "   - VPC/Subnet issues"
echo "   - Route table problems"

echo ""
echo "🔧 Step 4: Recovery Actions"
echo "==========================="
echo "Try these actions in order:"
echo ""
echo "1. **Restart Instance** (if stopped):"
echo "   - AWS Console → EC2 → Instances"
echo "   - Select instance → Actions → Instance State → Start"
echo ""
echo "2. **Reboot Instance** (if running but unresponsive):"
echo "   - AWS Console → EC2 → Instances"
echo "   - Select instance → Actions → Instance State → Reboot"
echo ""
echo "3. **Check System Logs**:"
echo "   - AWS Console → EC2 → Instances"
echo "   - Select instance → Actions → Monitor and troubleshoot → Get system log"
echo ""
echo "4. **Resize Instance** (if memory issues):"
echo "   - Consider upgrading to t2.small (2GB RAM) or t3.small"
echo "   - Stop instance → Change instance type → Start"

if [ "$SSH_WORKING" = true ]; then
    echo ""
    echo "🔍 Step 5: Server Diagnostics (SSH Available)"
    echo "=============================================="
    echo "Since SSH is working, let's check the server status..."
    
    ssh -i "$KEY_PATH" "$EC2_USER@$EC2_IP" << 'EOF'
        echo "📊 System Status:"
        echo "Uptime: $(uptime)"
        echo "Load average: $(cat /proc/loadavg)"
        echo ""
        echo "💾 Memory Usage:"
        free -h
        echo ""
        echo "💽 Disk Usage:"
        df -h /
        echo ""
        echo "🐍 Python Processes:"
        ps aux | grep python | grep -v grep || echo "No Python processes running"
        echo ""
        echo "🌐 Nginx Status:"
        sudo systemctl status nginx --no-pager -l | head -10
        echo ""
        echo "📋 Recent System Logs:"
        sudo journalctl --no-pager -l -n 20
        echo ""
        echo "📋 Application Logs:"
        if [ -f "/home/ubuntu/pesticide-search/app.log" ]; then
            echo "Recent app.log entries:"
            tail -20 /home/ubuntu/pesticide-search/app.log
        else
            echo "No app.log found"
        fi
EOF
else
    echo ""
    echo "⚠️  SSH Not Available - Manual AWS Console Check Required"
    echo "========================================================"
    echo "Since SSH is not working, you need to:"
    echo "1. Check AWS Console for instance status"
    echo "2. Restart/reboot the instance if needed"
    echo "3. Check system logs in AWS Console"
    echo "4. Verify security group settings"
fi

echo ""
echo "🔧 Step 6: Prevention for Future"
echo "================================"
echo "To prevent future crashes:"
echo ""
echo "1. **Upgrade Instance Type**:"
echo "   - t2.micro → t2.small (2GB RAM vs 1GB)"
echo "   - Better performance and stability"
echo ""
echo "2. **Implement Proper Monitoring**:"
echo "   - CloudWatch alarms for CPU/Memory"
echo "   - Auto-scaling groups"
echo "   - Health checks"
echo ""
echo "3. **Use Systemd Services**:"
echo "   - Automatic restart on crash"
echo "   - Proper logging"
echo "   - Service management"
echo ""
echo "4. **Optimize Memory Usage**:"
echo "   - Database instead of JSON files"
echo "   - Lazy loading"
echo "   - Memory limits"

echo ""
echo "📞 Next Steps:"
echo "=============="
echo "1. Check AWS Console immediately"
echo "2. Restart the instance if it's stopped"
echo "3. If it's running but unresponsive, reboot it"
echo "4. Once back online, run the stable deployment script"
echo "5. Consider upgrading to a larger instance type"
echo ""
echo "🔗 Useful AWS Console Links:"
echo "   EC2 Dashboard: https://console.aws.amazon.com/ec2/"
echo "   Your Instance: https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#Instances:instanceId=i-xxxxxxxxx"
echo ""
echo "Run this script again after restarting the instance to verify recovery."



