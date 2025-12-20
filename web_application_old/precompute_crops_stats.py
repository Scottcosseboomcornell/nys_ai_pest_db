#!/usr/bin/env python3
"""
Precompute crops list and statistics for faster page loading.
This script generates a JSON file with:
- Top 20 crops (alphabetically sorted)
- Total pesticide count
- Total active ingredients count
- Last updated timestamp
"""

import json
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pesticide_search import load_pesticide_data

def get_crop_grouping():
    """Get crop grouping logic from pesticide_search.py"""
    return {
        'normalized_to_originals': {
            'Almond': ['almond', 'almonds'],
            'Apple': ['apple', 'apples', 'apple tree', 'apple trees'],
            'Apricot': ['apricot', 'apricots'],
            'Blackberry': ['blackberry', 'blackberries'],
            'Blueberry': ['blueberry', 'blueberries'],
            'Broccoli': ['broccoli'],
            'Cherry': ['cherry', 'cherries'],
            'Cranberry': ['cranberry', 'cranberries'],
            'Cucumber': ['cucumber', 'cucumbers'],
            'Grape': ['grape', 'grapes', 'grapevine', 'grapevines'],
            'Nectarine': ['nectarine', 'nectarines'],
            'Orange': ['orange', 'oranges'],
            'Peach': ['peach', 'peaches'],
            'Pear': ['pear', 'pears'],
            'Pecan': ['pecan', 'pecans'],
            'Pepper': ['pepper', 'peppers'],
            'Potato': ['potato', 'potatoes'],
            'Raspberry': ['raspberry', 'raspberries'],
            'Spinach': ['spinach'],
            'Strawberry': ['strawberry', 'strawberries']
        }
    }

def precompute_crops_and_stats():
    """Precompute crops list and statistics"""
    print("Loading pesticide data...")
    data = load_pesticide_data()
    print(f"Loaded {len(data)} pesticide records")
    
    # Get crop grouping
    crop_grouping = get_crop_grouping()
    
    # Count crops
    crop_counts = defaultdict(int)
    for pesticide in data:
        for app in pesticide.get('application_info', []):
            crops = [c.strip().lower() for c in (app.get('Target_Crop', '') or '').split(',') if c.strip()]
            for crop in crops:
                # Find which normalized crop this belongs to
                for normalized_crop, original_variants in crop_grouping['normalized_to_originals'].items():
                    if crop in original_variants:
                        crop_counts[normalized_crop] += 1
                        break
    
    # Get top 20 crops alphabetically
    top_crops = sorted(crop_counts.keys())[:20]
    
    # Count unique active ingredients
    unique_ingredients = set()
    for pesticide in data:
        for ing in pesticide.get('active_ingredients', []):
            if ing.get('name', '').strip():
                unique_ingredients.add(ing['name'].strip())
    
    # Generate precomputed data
    precomputed_data = {
        "crops": top_crops,
        "total_pesticides": len(data),
        "total_active_ingredients": len(unique_ingredients),
        "last_updated": datetime.now().isoformat(),
        "crop_counts": dict(crop_counts)
    }
    
    # Save to file
    output_path = "precomputed_crops_stats.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(precomputed_data, f, indent=2)
    
    print(f"✅ Precomputed crops and stats saved to {output_path}")
    print(f"📊 Top 20 crops: {top_crops}")
    print(f"📊 Total pesticides: {len(data)}")
    print(f"📊 Total active ingredients: {len(unique_ingredients)}")
    
    return precomputed_data

if __name__ == "__main__":
    precompute_crops_and_stats()





