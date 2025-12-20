# Web Application Crash Fix - Complete Solution

## Problem Summary
Your web application was crashing every few days due to:
1. **No process management** - Flask app running with `nohup` without auto-restart
2. **Memory issues** - Loading 15,000+ JSON files causing OOM crashes on t2.micro (1GB RAM)
3. **No health monitoring** - No system to detect crashes and restart
4. **Port conflicts** - Inconsistent port usage causing nginx proxy issues

## Immediate Fix (502 Bad Gateway)

### Quick Fix Script
```bash
./quick_fix_502.sh /path/to/your/pesticide-search-key-new.pem
```

This will:
- Stop all existing processes
- Start Flask app on port 5001
- Configure nginx properly
- Test the application

## Permanent Solution

### Stable Deployment Script
```bash
./deploy_stable_solution.sh
```

This implements:
- **Systemd services** for proper process management
- **Health monitoring** with automatic restart
- **Memory limits** to prevent OOM crashes
- **Proper logging** and error tracking
- **Service management** with auto-start on boot

## What the Stable Solution Includes

### 1. Systemd Service Files
- `pesticide-search.service` - Main application service
- `health-monitor.service` - Health monitoring service

### 2. Health Monitoring
- `health_monitor.py` - Monitors app health every 60 seconds
- Automatic restart after 3 consecutive failures
- Logging of all health check events

### 3. Memory Management
- Memory limit of 800MB to prevent OOM crashes
- CPU quota of 80% to prevent resource exhaustion
- Proper resource cleanup

### 4. Enhanced Flask App
- Health check endpoint at `/health`
- Threaded operation for better performance
- Proper error handling and logging

## Service Management Commands

### Check Status
```bash
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'sudo systemctl status pesticide-search health-monitor nginx'
```

### View Logs
```bash
# Application logs
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'journalctl -u pesticide-search -f'

# Health monitor logs
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'journalctl -u health-monitor -f'
```

### Restart Services
```bash
# Restart main application
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'sudo systemctl restart pesticide-search'

# Restart health monitor
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'sudo systemctl restart health-monitor'

# Restart nginx
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'sudo systemctl restart nginx'
```

## Monitoring and Testing

### Health Check
```bash
curl http://3.144.200.224/health
```

### API Test
```bash
curl http://3.144.200.224/api/stats
```

### Web Interface
- Main site: http://3.144.200.224
- Pesticide database: http://3.144.200.224/pesticide-database

## Troubleshooting

### If Application Still Crashes

1. **Check memory usage:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'free -h'
   ```

2. **Check system resources:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'htop'
   ```

3. **Check service logs:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'journalctl -u pesticide-search --since "1 hour ago"'
   ```

### If 502 Error Persists

1. **Check if Flask is running:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'ps aux | grep python'
   ```

2. **Check port status:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'sudo netstat -tlnp | grep :5001'
   ```

3. **Test local connection:**
   ```bash
   ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'curl -s http://localhost:5001/health'
   ```

## Performance Optimizations

### Memory Usage
- The app now has a 800MB memory limit
- Data is cached efficiently with 1-hour timeout
- Search indexing reduces memory footprint

### CPU Usage
- CPU quota limited to 80% to prevent resource exhaustion
- Threaded Flask operation for better concurrency

### Monitoring
- Health checks every 60 seconds
- Automatic restart on failure
- Comprehensive logging

## Long-term Recommendations

### 1. Upgrade EC2 Instance
Consider upgrading from t2.micro to t2.small or t3.small for:
- More memory (2GB vs 1GB)
- Better CPU performance
- More stable operation

### 2. Database Migration
Consider migrating from JSON files to a proper database:
- SQLite for simple setup
- PostgreSQL for better performance
- Reduced memory usage
- Better query performance

### 3. Load Balancing
For high traffic:
- Multiple application instances
- Load balancer (ALB)
- Auto-scaling groups

## Files Created

### Service Files
- `pesticide-search.service` - Main application service
- `health-monitor.service` - Health monitoring service

### Scripts
- `deploy_stable_solution.sh` - Complete stable deployment
- `quick_fix_502.sh` - Immediate 502 fix
- `health_monitor.py` - Health monitoring script

### Enhanced Application
- Updated `pesticide_search.py` with health endpoint
- Better error handling and logging
- Threaded operation

## Deployment Steps

1. **Immediate fix:** Run `./quick_fix_502.sh` to get your site working
2. **Permanent solution:** Run `./deploy_stable_solution.sh` for stable operation
3. **Monitor:** Use the monitoring commands to track health
4. **Maintain:** Regular health checks and log monitoring

This solution should eliminate the crashes and provide a stable, monitored web application that automatically recovers from issues.




