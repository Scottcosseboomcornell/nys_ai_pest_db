#!/usr/bin/env python3
"""
Test script for the filtered pesticide download functionality
"""

import requests
import json
import os

def test_filtered_download_endpoint():
    """Test the filtered download endpoint with sample filter parameters"""
    
    print("🧪 Testing filtered download endpoint...")
    
    # Test with sample crop and pest filters
    test_cases = [
        {"crop": "Apple", "pest": "Apple Scab"},
        {"crop": "Tomato", "pest": ""},
        {"crop": "", "pest": "Powdery Mildew"},
        {"crop": "Grape", "pest": "Botrytis"}
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        crop = test_case["crop"]
        pest = test_case["pest"]
        
        print(f"\n📋 Test Case {i}: Crop='{crop}', Pest='{pest}'")
        
        # Build the URL
        params = []
        if crop:
            params.append(f"crop={crop}")
        if pest:
            params.append(f"pest={pest}")
        
        url = f"http://localhost:5001/api/filter/download?{'&'.join(params)}"
        
        try:
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                print("✅ Download endpoint working correctly!")
                print(f"📄 Content-Type: {response.headers.get('Content-Type')}")
                print(f"📁 Content-Disposition: {response.headers.get('Content-Disposition')}")
                print(f"📊 File size: {len(response.content)} bytes")
                
                # Save the file for inspection
                filename = f"test_filtered_download_{i}_{crop or 'no_crop'}_{pest or 'no_pest'}.xlsx"
                filename = filename.replace(' ', '_').replace('/', '_')
                
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"💾 Test file saved as: {filename}")
                
            elif response.status_code == 404:
                print("ℹ️  No results found for these filters (expected for some test cases)")
                
            else:
                print(f"❌ Download failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            print("💡 Make sure the Flask app is running on port 5001")

if __name__ == "__main__":
    test_filtered_download_endpoint()


