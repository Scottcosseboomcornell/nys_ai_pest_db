#!/usr/bin/env python3
"""
Test script to debug the search bug
"""

import json
import os
import glob
from collections import defaultdict

def test_search_logic():
    """Test the exact search logic used in the server"""
    
    OUTPUT_JSON_DIR = "altered_json"
    pesticide_data = []
    search_index = defaultdict(list)
    
    print("Loading pesticide data...")
    
    # Get all JSON files
    json_files = glob.glob(os.path.join(OUTPUT_JSON_DIR, "*.json"))
    print(f"Found {len(json_files)} JSON files")
    
    for i, json_file in enumerate(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if 'pesticide' in data:
                    pesticide = data['pesticide']
                    
                    # Extract basic info
                    trade_name = pesticide.get('trade_Name', 'N/A')
                    epa_reg_no = pesticide.get('epa_reg_no', 'N/A')
                    company_name = pesticide.get('COMPANY_NAME', 'N/A')
                    abns = pesticide.get('ABNS', 'N/A')
                    
                    pesticide_info = {
                        'epa_reg_no': epa_reg_no,
                        'trade_Name': trade_name,
                        'COMPANY_NAME': company_name,
                        'ABNS': abns,
                        'filename': os.path.basename(json_file)
                    }
                    pesticide_data.append(pesticide_info)
                    
                    # Build search index - EXACTLY like the server does
                    index = len(pesticide_data) - 1
                    
                    # Index by trade name
                    trade_lower = trade_name.lower()
                    search_index[f"trade:{trade_lower}"].append(index)
                    
                    # Index by company name
                    company_lower = company_name.lower()
                    search_index[f"company:{company_lower}"].append(index)
                    
                    # Index by ABNS (this might contain additional names)
                    abns_lower = abns.lower()
                    search_index[f"abns:{abns_lower}"].append(index)
                    
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
            continue
    
    print(f"Loaded {len(pesticide_data)} pesticides")
    print(f"Search index has {len(search_index)} entries")
    
    # Test search for "champ" - EXACTLY like the server does
    print("\nTesting search for 'champ' using server logic:")
    query = "champ"
    results = []
    seen_indices = set()
    
    # Search all indices for partial matches - EXACTLY like the server
    for key, indices in search_index.items():
        if query in key:  # Check if query is in the key (after prefix)
            print(f"Found match in key: {key}")
            for idx in indices:
                if idx not in seen_indices:
                    results.append(pesticide_data[idx])
                    seen_indices.add(idx)
                    print(f"  Added result {idx}: {pesticide_data[idx]['trade_Name']}")
    
    print(f"\nTotal results for 'champ': {len(results)}")
    print("First 5 results:")
    for i, result in enumerate(results[:5]):
        print(f"  {i+1}. {result['trade_Name']} (EPA: {result['epa_reg_no']})")
        print(f"     ABNS: {result['ABNS'][:100]}...")
        print()
    
    # Let's also check what keys contain "champ"
    print("Keys containing 'champ':")
    champ_keys = [key for key in search_index.keys() if 'champ' in key]
    for key in champ_keys[:10]:  # Show first 10
        print(f"  {key}")
        for idx in search_index[key]:
            print(f"    -> {pesticide_data[idx]['trade_Name']}")

if __name__ == "__main__":
    test_search_logic() 