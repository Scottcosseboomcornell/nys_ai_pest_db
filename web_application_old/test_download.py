#!/usr/bin/env python3
"""
Test script for the pesticide download functionality
"""

import requests
import json
import os

def test_download_endpoint():
    """Test the download endpoint with a sample EPA registration number"""
    
    # Start the Flask app in a separate process or use an existing one
    # For now, let's test the endpoint directly
    
    # Find a sample JSON file to test with
    json_dir = "../pipeline_critical_docs/altered_json"
    json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
    
    if not json_files:
        print("❌ No JSON files found for testing")
        return
    
    # Use the first JSON file
    sample_file = json_files[0]
    epa_reg_no = sample_file.replace('.json', '')
    
    print(f"🧪 Testing download with EPA registration number: {epa_reg_no}")
    
    # Test the download endpoint
    url = f"http://localhost:5001/api/pesticide/{epa_reg_no}/download"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            print("✅ Download endpoint working correctly!")
            print(f"📄 Content-Type: {response.headers.get('Content-Type')}")
            print(f"📁 Content-Disposition: {response.headers.get('Content-Disposition')}")
            print(f"📊 File size: {len(response.content)} bytes")
            
            # Save the file for inspection
            filename = f"test_download_{epa_reg_no}.xlsx"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"💾 Test file saved as: {filename}")
            
        else:
            print(f"❌ Download failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        print("💡 Make sure the Flask app is running on port 5001")

if __name__ == "__main__":
    test_download_endpoint()


