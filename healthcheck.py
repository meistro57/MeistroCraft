#!/usr/bin/env python3
"""
Health check script for MeistroCraft Docker container
"""

import sys
import requests
import time

def check_health():
    """Check if the MeistroCraft service is healthy"""
    try:
        # Test the health endpoint
        response = requests.get('http://localhost:8000/health', timeout=10)
        
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == '__main__':
    # Wait a bit for the service to start
    time.sleep(2)
    
    if check_health():
        sys.exit(0)
    else:
        sys.exit(1)