#!/usr/bin/env python3
"""
Target Lookup Module
Maps original target names to refined target names and types
"""

import pandas as pd
import os
from collections import defaultdict

# Load the target lookup data
def load_target_lookup_data():
    """Load the target lookup data from Excel file"""
    excel_file = "../pipeline_critical_docs/targetpest_types_names_lookup.xlsx"
    
    if not os.path.exists(excel_file):
        print(f"❌ Error: Target lookup file not found at {excel_file}")
        return None
    
    try:
        df = pd.read_excel(excel_file)
        
        # Clean up the data - remove rows with missing key information
        df = df.dropna(subset=['Original_Target', 'Newest_simplified_name', 'Targtype'])
        
        # Clean up target types - remove extra spaces and standardize
        df['Targtype'] = df['Targtype'].str.strip()
        df['Targtype'] = df['Targtype'].replace('Weed ', 'Weed')  # Fix extra space
        
        print(f"✅ Loaded target lookup data: {len(df)} entries")
        print(f"📊 Target types: {sorted(df['Targtype'].unique())}")
        print(f"📊 Unique simplified targets: {df['Newest_simplified_name'].nunique()}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error loading target lookup data: {e}")
        return None

# Global variable to store the lookup data
_target_lookup_df = None

def get_target_lookup_data():
    """Get the target lookup data, loading it if necessary"""
    global _target_lookup_df
    if _target_lookup_df is None:
        _target_lookup_df = load_target_lookup_data()
    return _target_lookup_df

def get_simplified_target(original_target):
    """
    Get the simplified target name for a given original target.
    If the simplified name contains commas, it will return the first target.
    
    Args:
        original_target (str): The original target name
        
    Returns:
        str: The simplified target name, or the original if no mapping exists
    """
    if not original_target or str(original_target).strip() in ['', 'N/A', 'nan']:
        return original_target
    
    df = get_target_lookup_data()
    if df is None:
        return original_target
    
    # Look for exact match
    match = df[df['Original_Target'] == str(original_target).strip()]
    if not match.empty:
        simplified_name = match.iloc[0]['Newest_simplified_name']
        # If the simplified name contains commas, return the first one
        if ',' in simplified_name:
            return simplified_name.split(',')[0].strip()
        return simplified_name
    
    return original_target

def get_simplified_targets_list(original_target):
    """
    Get a list of simplified target names for a given original target.
    Splits comma-separated targets into individual targets.
    
    Args:
        original_target (str): The original target name
        
    Returns:
        list: List of simplified target names
    """
    if not original_target or str(original_target).strip() in ['', 'N/A', 'nan']:
        return [original_target] if original_target else []
    
    df = get_target_lookup_data()
    if df is None:
        return [original_target]
    
    # Look for exact match
    match = df[df['Original_Target'] == str(original_target).strip()]
    if not match.empty:
        simplified_name = match.iloc[0]['Newest_simplified_name']
        # Split by comma and clean up each target
        if ',' in simplified_name:
            return [target.strip() for target in simplified_name.split(',') if target.strip()]
        return [simplified_name]
    
    return [original_target]

def get_target_type(original_target):
    """
    Get the target type for a given original target.
    
    Args:
        original_target (str): The original target name
        
    Returns:
        str: The target type, or 'Other' if no mapping exists
    """
    if not original_target or str(original_target).strip() in ['', 'N/A', 'nan']:
        return 'Other'
    
    df = get_target_lookup_data()
    if df is None:
        return 'Other'
    
    # Look for exact match
    match = df[df['Original_Target'] == str(original_target).strip()]
    if not match.empty:
        return match.iloc[0]['Targtype']
    
    return 'Other'

def get_target_specification(original_target):
    """
    Get the specification for a given original target.
    
    Args:
        original_target (str): The original target name
        
    Returns:
        str: The specification, or empty string if no mapping exists
    """
    if not original_target or str(original_target).strip() in ['', 'N/A', 'nan']:
        return ''
    
    df = get_target_lookup_data()
    if df is None:
        return ''
    
    # Look for exact match
    match = df[df['Original_Target'] == str(original_target).strip()]
    if not match.empty:
        spec = match.iloc[0]['Specification']
        return str(spec) if pd.notna(spec) else ''
    
    return ''

def get_target_organism(original_target):
    """
    Get the organism for a given original target.
    
    Args:
        original_target (str): The original target name
        
    Returns:
        str: The organism, or empty string if no mapping exists
    """
    if not original_target or str(original_target).strip() in ['', 'N/A', 'nan']:
        return ''
    
    df = get_target_lookup_data()
    if df is None:
        return ''
    
    # Look for exact match
    match = df[df['Original_Target'] == str(original_target).strip()]
    if not match.empty:
        organism = match.iloc[0]['Organism']
        return str(organism) if pd.notna(organism) else ''
    
    return ''

def get_all_target_types():
    """
    Get all unique target types.
    
    Returns:
        list: Sorted list of all target types
    """
    df = get_target_lookup_data()
    if df is None:
        return ['Other']
    
    target_types = df['Targtype'].dropna().unique()
    return sorted([t for t in target_types if t and t.strip()])

def get_simplified_targets_for_crop_and_type(crop, target_type):
    """
    Get simplified targets for a specific crop and target type.
    
    Args:
        crop (str): The crop name
        target_type (str): The target type
        
    Returns:
        list: Sorted list of simplified target names
    """
    df = get_target_lookup_data()
    if df is None:
        return []
    
    # Filter by target type
    filtered_df = df[df['Targtype'] == target_type]
    
    # If crop is specified, we need to check which targets are associated with that crop
    # This would require cross-referencing with the pesticide data
    # For now, return all targets of the specified type
    simplified_targets = filtered_df['Newest_simplified_name'].dropna().unique()
    return sorted([t for t in simplified_targets if t and t.strip()])

def get_original_targets_for_simplified_target(simplified_target):
    """
    Get all original targets that map to a simplified target.
    Handles comma-separated targets by checking if any part of the simplified name matches.
    
    Args:
        simplified_target (str): The simplified target name
        
    Returns:
        list: List of original target names
    """
    df = get_target_lookup_data()
    if df is None:
        return []
    
    original_targets = []
    
    # Check for exact matches
    exact_matches = df[df['Newest_simplified_name'] == simplified_target]
    original_targets.extend(exact_matches['Original_Target'].tolist())
    
    # Check for comma-separated matches (where the simplified target is part of a comma-separated list)
    for _, row in df.iterrows():
        simplified_name = str(row['Newest_simplified_name'])
        if ',' in simplified_name:
            # Split the comma-separated targets
            targets = [target.strip() for target in simplified_name.split(',')]
            if simplified_target in targets:
                original_targets.append(row['Original_Target'])
    
    return list(set(original_targets))  # Remove duplicates

if __name__ == "__main__":
    # Test the lookup functions
    print("🧪 Testing target lookup functions...")
    
    # Test individual lookups
    test_targets = ['Aphids', 'Powdery Mildew', 'Broadleaf Weeds', 'N/A']
    for target in test_targets:
        simplified = get_simplified_target(target)
        target_type = get_target_type(target)
        spec = get_target_specification(target)
        organism = get_target_organism(target)
        print(f"   {target} → {simplified} ({target_type}) - Spec: {spec}, Org: {organism}")
    
    # Test target types
    target_types = get_all_target_types()
    print(f"\n📊 Available target types: {target_types}")
    
    # Test simplified targets for a type
    insect_targets = get_simplified_targets_for_crop_and_type('Apple', 'Insect')
    print(f"\n🐛 Insect targets (first 10): {insect_targets[:10]}")
    
    # Test reverse lookup
    if insect_targets:
        original_targets = get_original_targets_for_simplified_target(insect_targets[0])
        print(f"\n🔄 Original targets for '{insect_targets[0]}': {original_targets[:5]}")
