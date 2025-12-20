#!/usr/bin/env python3
"""
Debug script to test search functionality
"""

import json
import os
import glob
from collections import defaultdict

def load_and_test_search():
    """Load data and test search functionality"""
    
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
                    
                    # Build search index
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
                    
                    # Check if this file contains "champ"
                    if 'champ' in trade_lower or 'champ' in abns_lower:
                        print(f"Found 'champ' in file {json_file}:")
                        print(f"  Trade Name: {trade_name}")
                        print(f"  ABNS: {abns}")
                        print(f"  Index: {index}")
                        print()
                        
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
            continue
    
    print(f"Loaded {len(pesticide_data)} pesticides")
    print(f"Search index has {len(search_index)} entries")
    
    # Test search for "champ"
    print("\nTesting search for 'champ':")
    query = "champ"
    results = []
    seen_indices = set()
    
    # Search in trade names
    trade_key = f"trade:{query}"
    if trade_key in search_index:
        print(f"Found {len(search_index[trade_key])} matches in trade names")
        for idx in search_index[trade_key]:
            if idx not in seen_indices:
                results.append(pesticide_data[idx])
                seen_indices.add(idx)
    
    # Search in ABNS
    abns_key = f"abns:{query}"
    if abns_key in search_index:
        print(f"Found {len(search_index[abns_key])} matches in ABNS")
        for idx in search_index[abns_key]:
            if idx not in seen_indices:
                results.append(pesticide_data[idx])
                seen_indices.add(idx)
    
    # Search in company names
    company_key = f"company:{query}"
    if company_key in search_index:
        print(f"Found {len(search_index[company_key])} matches in company names")
        for idx in search_index[company_key]:
            if idx not in seen_indices:
                results.append(pesticide_data[idx])
                seen_indices.add(idx)
    
    print(f"\nTotal results for 'champ': {len(results)}")
    for result in results[:5]:  # Show first 5 results
        print(f"  - {result['trade_Name']} (EPA: {result['epa_reg_no']})")
        print(f"    ABNS: {result['ABNS']}")
        print()
    
    # Test search for "acelepryn"
    print("\nTesting search for 'acelepryn':")
    query = "acelepryn"
    results = []
    seen_indices = set()
    
    # Search in trade names
    trade_key = f"trade:{query}"
    if trade_key in search_index:
        print(f"Found {len(search_index[trade_key])} matches in trade names")
        for idx in search_index[trade_key]:
            if idx not in seen_indices:
                results.append(pesticide_data[idx])
                seen_indices.add(idx)
    
    # Search in ABNS
    abns_key = f"abns:{query}"
    if abns_key in search_index:
        print(f"Found {len(search_index[abns_key])} matches in ABNS")
        for idx in search_index[abns_key]:
            if idx not in seen_indices:
                results.append(pesticide_data[idx])
                seen_indices.add(idx)
    
    print(f"\nTotal results for 'acelepryn': {len(results)}")
    for result in results[:5]:  # Show first 5 results
        print(f"  - {result['trade_Name']} (EPA: {result['epa_reg_no']})")
        print(f"    ABNS: {result['ABNS']}")
        print()

if __name__ == "__main__":
    load_and_test_search() 