#!/usr/bin/env python3
"""
Script to generate a CSV file of all unique target options with suggested consolidations and target types
This will help create a manual lookup table to simplify the target dropdown list
"""

import sys
import os
import pandas as pd
from collections import defaultdict

# Add the parent directory to the path so we can import the main module
sys.path.append('..')
from pesticide_search import load_pesticide_data

def analyze_targets():
    """Generate a CSV file with all unique target options and suggested consolidations"""
    
    print("🔍 Loading pesticide data...")
    data = load_pesticide_data()
    
    print("📊 Analyzing target options...")
    
    # Dictionary to store target counts and examples
    target_info = defaultdict(lambda: {'count': 0, 'examples': set()})
    
    for pesticide in data:
        # Get all applications for this pesticide
        applications = pesticide.get('application_info', [])
        
        for app in applications:
            target_disease_pest = app.get('Target_Disease_Pest', '')
            trade_name = pesticide.get('trade_Name', 'N/A')
            
            if target_disease_pest and target_disease_pest.strip():
                # Split by comma and clean up each individual target
                targets = [target.strip() for target in target_disease_pest.split(',') if target.strip()]
                
                for target in targets:
                    target_info[target]['count'] += 1
                    # Store up to 5 examples for each target
                    if len(target_info[target]['examples']) < 5:
                        target_info[target]['examples'].add(trade_name)
    
    # Convert to list for CSV
    csv_data = []
    for target, info in sorted(target_info.items()):
        csv_data.append({
            'Original_Target': target,
            'Count': info['count'],
            'Examples': '; '.join(list(info['examples'])),
            'Suggested_Simplified_Target': '',  # Empty for manual filling
            'Target_Type': '',  # Empty for manual filling (Disease, Insect, Weed, Vertebrate, Other)
            'Notes': ''  # Empty for manual notes
        })
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(csv_data)
    
    # Save to CSV
    output_file = 'target_analysis.csv'
    df.to_csv(output_file, index=False)
    
    print(f"✅ Generated {output_file} with {len(csv_data)} unique targets")
    print(f"📊 Total pesticides analyzed: {len(data)}")
    print(f"📈 Targets with most pesticides:")
    
    # Show top 20 targets by count
    top_targets = sorted(target_info.items(), key=lambda x: x[1]['count'], reverse=True)[:20]
    for target, info in top_targets:
        print(f"   {target}: {info['count']} pesticides")
    
    print(f"\n📝 Next steps:")
    print(f"   1. Open {output_file} in Excel or a text editor")
    print(f"   2. Fill in the 'Suggested_Simplified_Target' column")
    print(f"   3. Fill in the 'Target_Type' column with: Disease, Insect, Weed, Vertebrate, or Other")
    print(f"   4. Add notes in the 'Notes' column for complex cases")
    print(f"   5. Examples of consolidations:")
    print(f"      - 'Aphids' and 'Green Aphids' → 'Aphids'")
    print(f"      - 'Powdery Mildew' and 'Powdery Mildew (Apple)' → 'Powdery Mildew'")
    print(f"      - 'Weeds' and 'Annual Weeds' → 'Weeds'")
    
    return output_file

if __name__ == "__main__":
    try:
        output_file = analyze_targets()
        print(f"\n🎉 Success! Check {output_file} for the analysis.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
