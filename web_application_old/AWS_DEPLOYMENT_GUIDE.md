# AWS Deployment Guide for Optimized Pesticide Search Application

## Overview
This guide provides step-by-step instructions for deploying the optimized pesticide search application to AWS EC2.

## Prerequisites

### 1. AWS Account Setup
- AWS account with EC2 access
- EC2 instance running Ubuntu
- Security group configured for web access
- SSH key pair for secure access

### 2. Local Requirements
- SSH key file (`pesticide-search-key-new.pem`)
- Python 3.7+ installed
- Required Python packages (Flask, requests)

## Quick Deployment

### Option 1: Automated Deployment (Recommended)
```bash
cd web_application
./deploy_optimized_to_aws.sh
```

### Option 2: Manual Deployment
Follow the step-by-step instructions below.

## Step-by-Step Deployment

### Step 1: Prepare Local Environment
```bash
# Navigate to web application directory
cd web_application

# Verify files exist
ls -la pesticide_search.py
ls -la templates/search.html
ls -la ../pipeline_critical_docs/altered_json/

# Make deployment script executable
chmod +x deploy_optimized_to_aws.sh
```

### Step 2: Verify AWS Configuration
```bash
# Check if SSH key exists
ls -la pesticide-search-key-new.pem

# Set correct permissions
chmod 400 pesticide-search-key-new.pem

# Test SSH connection
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 "echo 'Connection successful'"
```

### Step 3: Run Deployment
```bash
# Execute the deployment script
./deploy_optimized_to_aws.sh
```

## AWS EC2 Instance Setup

### Instance Requirements
- **Type**: t3.medium or larger (recommended for 15,000+ records)
- **OS**: Ubuntu 20.04 LTS or newer
- **Storage**: At least 10GB free space
- **Memory**: 4GB RAM minimum

### Security Group Configuration
```
Inbound Rules:
- SSH (Port 22): Your IP address
- HTTP (Port 80): 0.0.0.0/0 (if using nginx)
- Custom TCP (Port 5001): 0.0.0.0/0 (Flask app)
```

### Initial Server Setup
```bash
# Connect to your EC2 instance
ssh -i pesticide-search-key-new.pem ubuntu@YOUR_EC2_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv -y

# Create application directory
mkdir -p /home/ubuntu/pesticide-search
cd /home/ubuntu/pesticide-search

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask requests
```

## Deployment Process

### What the Deployment Script Does

1. **File Verification**: Checks all required files exist
2. **SSH Connection**: Tests connection to AWS instance
3. **File Transfer**: Copies application files to server
4. **Data Transfer**: Compresses and transfers pesticide data
5. **Application Setup**: Installs dependencies and starts app
6. **Verification**: Tests API endpoints and confirms functionality

### Files Deployed
- `pesticide_search.py` - Optimized backend application
- `templates/` - HTML templates for web interface
- `test_performance.py` - Performance testing script
- `altered_json/` - Pesticide data (15,000+ JSON files)

## Post-Deployment Verification

### 1. Check Application Status
```bash
# SSH into your instance
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224

# Check if application is running
ps aux | grep python

# View application logs
tail -f /home/ubuntu/pesticide-search/app_optimized.log
```

### 2. Test API Endpoints
```bash
# Test statistics endpoint
curl -s http://localhost:5001/api/stats

# Test search endpoint
curl -s "http://localhost:5001/api/search?q=glyphosate&type=both"

# Test pagination endpoint
curl -s "http://localhost:5001/api/pesticides?page=1&per_page=5"
```

### 3. Performance Testing
```bash
# Run performance tests
cd /home/ubuntu/pesticide-search
python test_performance.py
```

## Accessing the Application

### Web Interface
- **URL**: http://3.144.200.224:5001/pesticide-database
- **Features**: Search, browse, and view detailed pesticide information

### API Endpoints
- **Stats**: http://3.144.200.224:5001/api/stats
- **Search**: http://3.144.200.224:5001/api/search?q=query&type=type
- **Pesticides**: http://3.144.200.224:5001/api/pesticides?page=1&per_page=50
- **Details**: http://3.144.200.224:5001/api/pesticide/{epa_reg_no}

## Monitoring and Maintenance

### Log Monitoring
```bash
# View real-time logs
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'tail -f /home/ubuntu/pesticide-search/app_optimized.log'

# Check application status
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'ps aux | grep python'
```

### Performance Monitoring
```bash
# Monitor system resources
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'htop'

# Check disk usage
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'df -h'

# Monitor memory usage
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'free -h'
```

### Cache Management
```bash
# Refresh cache (if data changes)
curl -X GET http://3.144.200.224:5001/api/cache/refresh
```

## Troubleshooting

### Common Issues

#### 1. SSH Connection Failed
```bash
# Check instance status in AWS Console
# Verify security group allows SSH (port 22)
# Ensure SSH key has correct permissions (400)
chmod 400 pesticide-search-key-new.pem
```

#### 2. Application Not Starting
```bash
# Check logs for errors
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'cat /home/ubuntu/pesticide-search/app_optimized.log'

# Verify Python environment
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'source /home/ubuntu/pesticide-search/venv/bin/activate && python --version'
```

#### 3. Data Not Loading
```bash
# Check if data files exist
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'ls -la /home/ubuntu/pesticide-search/altered_json/ | wc -l'

# Verify data integrity
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'cd /home/ubuntu/pesticide-search && python -c "import json; print(len([f for f in os.listdir(\"altered_json\") if f.endswith(\".json\")]))"'
```

#### 4. Performance Issues
```bash
# Check system resources
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'htop'

# Monitor application performance
ssh -i pesticide-search-key-new.pem ubuntu@3.144.200.224 'cd /home/ubuntu/pesticide-search && python test_performance.py'
```

## Scaling Considerations

### For High Traffic
1. **Load Balancer**: Use AWS Application Load Balancer
2. **Multiple Instances**: Deploy across multiple EC2 instances
3. **Database**: Consider migrating to RDS for better performance
4. **Caching**: Implement Redis for distributed caching

### For Large Datasets
1. **Database Migration**: Move from JSON files to PostgreSQL
2. **Search Engine**: Implement Elasticsearch for full-text search
3. **CDN**: Use CloudFront for static asset delivery
4. **Compression**: Enable gzip compression

## Security Best Practices

### Network Security
- Use HTTPS with SSL certificates
- Restrict access to specific IP ranges
- Implement rate limiting
- Use AWS WAF for additional protection

### Application Security
- Keep dependencies updated
- Implement input validation
- Use environment variables for sensitive data
- Regular security audits

## Cost Optimization

### EC2 Instance Types
- **Development**: t3.micro (free tier eligible)
- **Production**: t3.medium or t3.large
- **High Performance**: c5.large or c5.xlarge

### Storage Optimization
- Use EBS gp3 volumes for better performance
- Implement data compression
- Regular cleanup of log files

## Backup and Recovery

### Data Backup
```bash
# Create backup of pesticide data
tar -czf pesticide_data_backup_$(date +%Y%m%d).tar.gz altered_json/

# Backup application files
tar -czf app_backup_$(date +%Y%m%d).tar.gz pesticide_search.py templates/
```

### Recovery Process
1. Restore data from backup
2. Redeploy application files
3. Restart application
4. Verify functionality

## Support and Maintenance

### Regular Maintenance Tasks
- Monitor application logs
- Check system resources
- Update dependencies
- Backup data regularly
- Test performance periodically

### Emergency Procedures
1. **Application Crash**: Restart with `nohup python pesticide_search.py > app.log 2>&1 &`
2. **Data Corruption**: Restore from backup
3. **Performance Issues**: Check logs and system resources
4. **Security Breach**: Review logs and update security groups

## Conclusion

The optimized pesticide search application is now deployed on AWS with:
- **Fast Performance**: Sub-5ms response times
- **Scalable Architecture**: Ready for growth
- **Comprehensive Monitoring**: Full visibility into application health
- **Easy Maintenance**: Automated deployment and monitoring tools

For additional support or questions, refer to the performance optimization documentation or contact the development team. 