#!/usr/bin/env python3
"""
Performance Testing Script for Pesticide Search Application
Tests the loading and search performance of the optimized application
"""

import time
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_api_endpoint(endpoint, description):
    """Test a single API endpoint and measure response time"""
    base_url = "http://localhost:5001"
    url = f"{base_url}{endpoint}"
    
    start_time = time.time()
    try:
        response = requests.get(url, timeout=30)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            print(f"✅ {description}: {response_time:.2f}ms")
            
            # Print additional info for specific endpoints
            if 'stats' in endpoint:
                print(f"   - Total pesticides: {data.get('total_pesticides', 'N/A')}")
                print(f"   - Unique ingredients: {data.get('unique_ingredients', 'N/A')}")
            elif 'pesticides' in endpoint:
                print(f"   - Pesticides returned: {len(data.get('pesticides', []))}")
                print(f"   - Total pages: {data.get('pagination', {}).get('pages', 'N/A')}")
            elif 'search' in endpoint:
                print(f"   - Search results: {len(data.get('results', []))}")
            
            return response_time, True
        else:
            print(f"❌ {description}: HTTP {response.status_code}")
            return 0, False
            
    except Exception as e:
        end_time = time.time()
        response_time = (end_time - start_time) * 1000
        print(f"❌ {description}: Error - {str(e)} ({response_time:.2f}ms)")
        return response_time, False

def test_search_performance():
    """Test search performance with various queries"""
    base_url = "http://localhost:5001"
    search_queries = [
        ("roundup", "Search for 'roundup'"),
        ("glyphosate", "Search for 'glyphosate'"),
        ("corn", "Search for 'corn'"),
        ("fungicide", "Search for 'fungicide'"),
        ("100-1000", "Search for EPA number '100-1000'"),
    ]
    
    print("\n🔍 Testing Search Performance:")
    print("=" * 50)
    
    for query, description in search_queries:
        endpoint = f"/api/search?q={query}&type=both"
        test_api_endpoint(endpoint, description)

def test_concurrent_requests():
    """Test concurrent request handling"""
    base_url = "http://localhost:5001"
    endpoints = [
        ("/api/stats", "Stats endpoint"),
        ("/api/pesticides?page=1&per_page=50", "First page"),
        ("/api/pesticides?page=2&per_page=50", "Second page"),
        ("/api/search?q=roundup&type=both", "Search 'roundup'"),
    ]
    
    print("\n🚀 Testing Concurrent Requests:")
    print("=" * 50)
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for endpoint, description in endpoints:
            future = executor.submit(test_api_endpoint, endpoint, description)
            futures.append((future, description))
        
        for future, description in futures:
            try:
                response_time, success = future.result(timeout=30)
            except Exception as e:
                print(f"❌ {description}: Concurrent test failed - {str(e)}")
    
    total_time = (time.time() - start_time) * 1000
    print(f"\n⏱️  Total concurrent test time: {total_time:.2f}ms")

def main():
    """Main performance test function"""
    print("🧪 Pesticide Search Application Performance Test")
    print("=" * 60)
    
    # Test basic endpoints
    print("\n📊 Testing Basic Endpoints:")
    print("=" * 50)
    
    test_api_endpoint("/api/stats", "Statistics endpoint")
    test_api_endpoint("/api/pesticides?page=1&per_page=50", "First page of pesticides")
    test_api_endpoint("/api/pesticides?page=2&per_page=50", "Second page of pesticides")
    
    # Test search performance
    test_search_performance()
    
    # Test concurrent requests
    test_concurrent_requests()
    
    print("\n✅ Performance test completed!")
    print("\n💡 Performance Tips:")
    print("- First load may be slower due to cache initialization")
    print("- Subsequent requests should be much faster")
    print("- Search performance depends on query complexity")
    print("- Consider using the cache refresh endpoint if data changes")

if __name__ == "__main__":
    main() 