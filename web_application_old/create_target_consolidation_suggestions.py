#!/usr/bin/env python3
"""
Script to create initial suggestions for target consolidations and target types
This provides a starting point for manual review and refinement
Uses product_type from JSON files to determine target types
"""

import pandas as pd
import json
from collections import defaultdict
from pathlib import Path

def load_json_files(json_dir):
    """Load all JSON files and build a mapping from targets to product types"""
    target_to_product_types = defaultdict(set)
    
    json_path = Path(json_dir)
    if not json_path.exists():
        # Try relative path from script location
        script_dir = Path(__file__).parent
        json_path = script_dir.parent / 'altered_json'
        if not json_path.exists():
            raise FileNotFoundError(f"Could not find altered_json directory. Tried: {json_dir} and {json_path}")
    
    json_files = list(json_path.glob('*.json'))
    print(f"📂 Loading {len(json_files)} JSON files from {json_path}...")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            pesticide = data.get('pesticide', {})
            if not isinstance(pesticide, dict):
                continue
            
            product_type_raw = pesticide.get('product_type', '').strip()
            if not product_type_raw:
                continue
            
            # Split comma-separated product types and normalize
            product_types_list = [pt.strip().upper() for pt in product_type_raw.split(',') if pt.strip()]
            if not product_types_list:
                continue
            
            # Extract all targets from Application_Info
            application_info = pesticide.get('Application_Info', [])
            if not isinstance(application_info, list):
                continue
            
            for app in application_info:
                target_disease_pest = app.get('Target_Disease_Pest', [])
                if not isinstance(target_disease_pest, list):
                    continue
                
                for target_obj in target_disease_pest:
                    if isinstance(target_obj, dict):
                        target_name = target_obj.get('name', '').strip()
                    else:
                        target_name = str(target_obj).strip()
                    
                    if target_name:
                        # Add all product types for this target
                        for pt in product_types_list:
                            target_to_product_types[target_name].add(pt)
        
        except Exception as e:
            print(f"⚠️  Warning: Error reading {json_file.name}: {e}")
            continue
    
    print(f"✅ Loaded {len(target_to_product_types)} unique targets")
    return target_to_product_types

def map_product_type_to_target_type(product_types):
    """Map product types to target types based on comprehensive mapping table"""
    if not product_types:
        return 'Other'
    
    # Convert to set and normalize to uppercase
    product_types_set = {pt.upper().strip() for pt in product_types if pt}
    
    if not product_types_set:
        return 'Other'
    
    # Check for specific type indicators
    has_growth_regulator = 'GROWTH REGULATOR' in product_types_set
    has_rodenticide = 'RODENTICIDE' in product_types_set
    has_avicide = 'AVICIDE' in product_types_set
    has_herbicide = 'HERBICIDE' in product_types_set
    has_defoliant = 'DEFOLIANT' in product_types_set
    has_fungicide = 'FUNGICIDE' in product_types_set
    has_nematicide = 'NEMATICIDE' in product_types_set
    has_insecticide = 'INSECTICIDE' in product_types_set
    has_miticide = 'MITICIDE' in product_types_set
    has_termite = 'TERMITICIDE' in product_types_set
    has_repellent = 'REPELLENT' in product_types_set
    has_mosquito = any('MOSQUITO' in pt for pt in product_types_set)
    has_antimicrobial = 'ANTIMICROBIAL' in product_types_set
    has_disinfectant = 'DISINFECTANT' in product_types_set
    has_sanitizer = 'SANITIZER' in product_types_set
    has_mildewstatic = 'MILDEWSTATIC' in product_types_set
    has_algaecide = 'ALGAECIDE' in product_types_set
    
    # Priority 1: Growth Regulator (only if it's the only type)
    if has_growth_regulator and len(product_types_set) == 1:
        return 'Growth Regul'
    
    # Priority 2: Vertebrate types
    if has_rodenticide or has_avicide:
        return 'Vertebrate'
    
    # Priority 3: Disease types
    # Based on table patterns, disease types take precedence in mixed combinations
    # when DISINFECTANT, SANITIZER, MILDEWSTATIC, or ANTIMICROBIAL are present
    has_disease_indicator = (has_fungicide or has_nematicide or has_antimicrobial or 
                             has_disinfectant or has_sanitizer or has_mildewstatic or has_algaecide)
    has_insect_indicator = (has_insecticide or has_miticide or has_termite or 
                           has_repellent or has_mosquito)
    
    # Special case: If both disease and insect indicators exist
    if has_disease_indicator and has_insect_indicator:
        # Disease wins if DISINFECTANT, SANITIZER, MILDEWSTATIC, or ANTIMICROBIAL present
        if has_disinfectant or has_sanitizer or has_mildewstatic or has_antimicrobial:
            return 'Disease'
        # Disease wins if FUNGICIDE or NEMATICIDE present
        if has_fungicide or has_nematicide:
            return 'Disease'
        # Otherwise insect wins
        return 'Insects'
    
    # Priority 4: Disease types (standalone)
    if has_disease_indicator:
        return 'Disease'
    
    # Priority 5: Insect types
    if has_insect_indicator:
        return 'Insects'
    
    # Priority 6: Weed types
    if has_herbicide or has_defoliant:
        return 'Weeds'
    
    # Unknown combination
    return 'Other'

def create_target_suggestions(json_dir='../altered_json'):
    """Create initial suggestions for target consolidations and types"""
    
    # Load JSON files and build target to product_type mapping
    target_to_product_types = load_json_files(json_dir)
    
    # Read the original analysis
    df = pd.read_csv('target_analysis.csv')
    
    # Create suggested mappings
    suggested_mapping = {}
    target_type_mapping = {}
    
    # Process each target
    for _, row in df.iterrows():
        original_target_raw = row['Original_Target']
        
        # Handle NaN values
        if pd.isna(original_target_raw):
            original_target = 'N/A'
        else:
            original_target = str(original_target_raw).strip()
        
        # Start with original as simplified target
        simplified_target = original_target if original_target != 'N/A' else 'N/A'
        target_type = 'Other'  # Default type
        
        # Skip N/A entries
        if original_target in ['N/A', 'n/a', 'na', 'none', '', 'nan']:
            simplified_target = 'N/A'
            target_type = 'Other'
        else:
            # Get product types for this target
            product_types = target_to_product_types.get(original_target, set())
            
            if product_types:
                # Map product types to target type
                target_type = map_product_type_to_target_type(product_types)
            else:
                # No product type found, set to Other
                target_type = 'Other'
        
        # Store the suggestions
        original_key = original_target
        suggested_mapping[original_key] = simplified_target
        target_type_mapping[original_key] = target_type
    
    # Apply the suggestions to the dataframe
    df['Suggested_Simplified_Target'] = df['Original_Target'].map(suggested_mapping)
    df['Target_Type'] = df['Original_Target'].map(target_type_mapping)
    
    # Add notes for special cases
    df.loc[df['Original_Target'] == 'N/A', 'Notes'] = 'No specific target'
    df.loc[df['Target_Type'] == 'Other', 'Notes'] = 'Multiple product types or no product type found'
    
    # Save the updated CSV
    output_file = 'target_analysis_with_suggestions.csv'
    df.to_csv(output_file, index=False)
    
    # Create a summary of the suggestions
    simplified_summary = df.groupby(['Suggested_Simplified_Target', 'Target_Type']).agg({
        'Count': 'sum',
        'Original_Target': lambda x: ', '.join(x.tolist()[:3]) + ('...' if len(x) > 3 else '')
    }).reset_index()
    
    simplified_summary.columns = ['Simplified_Target', 'Target_Type', 'Total_Count', 'Original_Targets']
    simplified_summary = simplified_summary.sort_values('Total_Count', ascending=False)
    
    summary_file = 'target_consolidation_summary.csv'
    simplified_summary.to_csv(summary_file, index=False)
    
    print(f"✅ Created {output_file} with initial suggestions")
    print(f"✅ Created {summary_file} with consolidation summary")
    print(f"\n📊 Target type distribution:")
    
    type_counts = df.groupby('Target_Type')['Count'].sum().sort_values(ascending=False)
    for target_type, count in type_counts.items():
        print(f"   {target_type}: {count} pesticides")
    
    print(f"\n📈 Top 15 simplified targets (by count):")
    for _, row in simplified_summary.head(15).iterrows():
        print(f"   {row['Simplified_Target']} ({row['Target_Type']}): {row['Total_Count']} pesticides")
    
    print(f"\n📈 Reduction: {len(df)} original targets → {len(simplified_summary)} simplified targets")
    print(f"   ({len(df) - len(simplified_summary)} targets consolidated)")
    
    return output_file, summary_file

if __name__ == "__main__":
    try:
        output_file, summary_file = create_target_suggestions()
        print(f"\n🎉 Success! Check {output_file} and {summary_file} for the suggestions.")
        print(f"\n📝 Next steps:")
        print(f"   1. Review the suggestions in {output_file}")
        print(f"   2. Modify any incorrect consolidations or target types")
        print(f"   3. Add notes for complex cases")
        print(f"   4. Use the final version to create a lookup table")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
