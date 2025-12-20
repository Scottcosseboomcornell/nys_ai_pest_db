#!/bin/bash

# Wait for Server to Come Back Online
# This script will continuously check if the server is responsive

echo "🔄 Waiting for server to come back online..."
echo "Server IP: 3.144.200.224"
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
    # Test ping
    if ping -c 1 -W 3 3.144.200.224 > /dev/null 2>&1; then
        echo "✅ $(date): Server is responding to ping"
        
        # Test SSH
        if ssh -i web_application/pesticide-search-key-new.pem -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@3.144.200.224 "echo 'SSH test'" > /dev/null 2>&1; then
            echo "✅ $(date): SSH connection successful"
            
            # Test HTTP
            if curl -s --connect-timeout 5 http://3.144.200.224/ > /dev/null 2>&1; then
                echo "✅ $(date): HTTP connection successful"
                echo ""
                echo "🎉 SERVER IS FULLY ONLINE!"
                echo "You can now run:"
                echo "  ./web_application/deploy_stable_solution.sh"
                echo ""
                break
            else
                echo "⚠️  $(date): SSH works but HTTP not responding (502 error likely)"
                echo "You can now run:"
                echo "  ./web_application/quick_fix_502.sh web_application/pesticide-search-key-new.pem"
                echo ""
                break
            fi
        else
            echo "⚠️  $(date): Ping works but SSH not responding"
        fi
    else
        echo "❌ $(date): Server not responding to ping"
    fi
    
    sleep 10
done



