#!/usr/bin/env python3
"""
Health Monitor for Pesticide Search Application
Monitors the Flask app and restarts it if it becomes unresponsive
"""

import requests
import time
import subprocess
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/pesticide-search/health_monitor.log'),
        logging.StreamHandler()
    ]
)

class HealthMonitor:
    def __init__(self, app_url="http://localhost:5001", check_interval=60):
        self.app_url = app_url
        self.check_interval = check_interval
        self.consecutive_failures = 0
        self.max_failures = 3
        
    def check_health(self):
        """Check if the application is responding"""
        try:
            response = requests.get(f"{self.app_url}/api/stats", timeout=10)
            if response.status_code == 200:
                self.consecutive_failures = 0
                return True
        except Exception as e:
            logging.warning(f"Health check failed: {e}")
            self.consecutive_failures += 1
        return False
    
    def restart_service(self):
        """Restart the systemd service"""
        try:
            logging.info("Restarting pesticide-search service...")
            subprocess.run(['sudo', 'systemctl', 'restart', 'pesticide-search'], check=True)
            time.sleep(10)  # Wait for service to start
            
            # Verify restart was successful
            if self.check_health():
                logging.info("Service restarted successfully")
                return True
            else:
                logging.error("Service restart failed - still not responding")
                return False
        except Exception as e:
            logging.error(f"Failed to restart service: {e}")
            return False
    
    def run(self):
        """Main monitoring loop"""
        logging.info("Starting health monitor...")
        
        while True:
            try:
                if not self.check_health():
                    logging.warning(f"Health check failed ({self.consecutive_failures}/{self.max_failures})")
                    
                    if self.consecutive_failures >= self.max_failures:
                        logging.error("Maximum failures reached, restarting service...")
                        if self.restart_service():
                            self.consecutive_failures = 0
                        else:
                            logging.error("Failed to restart service, will retry in next cycle")
                else:
                    if self.consecutive_failures > 0:
                        logging.info("Service is healthy again")
                        self.consecutive_failures = 0
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logging.info("Health monitor stopped by user")
                break
            except Exception as e:
                logging.error(f"Unexpected error in health monitor: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = HealthMonitor()
    monitor.run()




