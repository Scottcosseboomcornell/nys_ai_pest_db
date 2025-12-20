#!/usr/bin/env python3
"""
Script to create initial suggestions for target consolidations and target types
This provides a starting point for manual review and refinement
"""

import pandas as pd
import re
from collections import defaultdict

def create_target_suggestions():
    """Create initial suggestions for target consolidations and types"""
    
    # Read the original analysis
    df = pd.read_csv('target_analysis.csv')
    
    # Create suggested mappings
    suggested_mapping = {}
    target_type_mapping = {}
    
    # Define patterns for different target types
    insect_patterns = [
        r'.*aphid.*', r'.*beetle.*', r'.*moth.*', r'.*caterpillar.*', r'.*worm.*',
        r'.*fly.*', r'.*thrip.*', r'.*mite.*', r'.*bug.*', r'.*weevil.*',
        r'.*hopper.*', r'.*borer.*', r'.*miner.*', r'.*roller.*', r'.*cutworm.*',
        r'.*armyworm.*', r'.*leafhopper.*', r'.*whitefly.*', r'.*mealybug.*',
        r'.*scale.*', r'.*spider.*', r'.*ant.*', r'.*wasp.*', r'.*bee.*',
        r'.*mosquito.*', r'.*gnat.*', r'.*midge.*', r'.*maggot.*', r'.*grub.*',
        r'.*larvae.*', r'.*nymph.*', r'.*adult.*insect.*', r'.*pest.*insect.*'
    ]
    
    disease_patterns = [
        r'.*mildew.*', r'.*mold.*', r'.*rot.*', r'.*blight.*', r'.*spot.*',
        r'.*rust.*', r'.*scab.*', r'.*anthracnose.*', r'.*canker.*', r'.*wilt.*',
        r'.*virus.*', r'.*bacteria.*', r'.*fungus.*', r'.*disease.*', r'.*pathogen.*',
        r'.*infection.*', r'.*lesion.*', r'.*necrosis.*', r'.*chlorosis.*',
        r'.*powdery.*', r'.*downy.*', r'.*black.*spot.*', r'.*brown.*spot.*',
        r'.*leaf.*spot.*', r'.*fruit.*rot.*', r'.*root.*rot.*', r'.*stem.*rot.*',
        r'.*crown.*rot.*', r'.*blossom.*rot.*', r'.*bacterial.*', r'.*fungal.*'
    ]
    
    weed_patterns = [
        r'.*weed.*', r'.*grass.*', r'.*broadleaf.*', r'.*annual.*grass.*',
        r'.*perennial.*grass.*', r'.*sedge.*', r'.*rush.*', r'.*bramble.*',
        r'.*thistle.*', r'.*dandelion.*', r'.*clover.*', r'.*plantain.*',
        r'.*chickweed.*', r'.*purslane.*', r'.*lambsquarters.*', r'.*pigweed.*',
        r'.*ragweed.*', r'.*bindweed.*', r'.*morning.*glory.*', r'.*knotweed.*',
        r'.*crabgrass.*', r'.*foxtail.*', r'.*barnyard.*grass.*', r'.*johnsongrass.*',
        r'.*bermudagrass.*', r'.*quackgrass.*', r'.*nutsedge.*', r'.*yellow.*nutsedge.*',
        r'.*purple.*nutsedge.*', r'.*wild.*oats.*', r'.*ryegrass.*', r'.*fescue.*'
    ]
    
    vertebrate_patterns = [
        r'.*rodent.*', r'.*mouse.*', r'.*rat.*', r'.*vole.*', r'.*gopher.*',
        r'.*mole.*', r'.*rabbit.*', r'.*deer.*', r'.*bird.*', r'.*squirrel.*',
        r'.*chipmunk.*', r'.*groundhog.*', r'.*prairie.*dog.*', r'.*beaver.*',
        r'.*raccoon.*', r'.*skunk.*', r'.*opossum.*', r'.*coyote.*', r'.*fox.*'
    ]
    
    # Process each target
    for _, row in df.iterrows():
        original_target_raw = row['Original_Target']
        
        # Handle NaN values
        if pd.isna(original_target_raw):
            original_target = 'n/a'
        else:
            original_target = str(original_target_raw).lower()
        
        simplified_target = str(original_target_raw) if not pd.isna(original_target_raw) else 'N/A'  # Start with original
        target_type = 'Other'  # Default type
        
        # Skip N/A entries
        if original_target in ['n/a', 'na', 'none', '', 'nan']:
            simplified_target = 'N/A'
            target_type = 'Other'
        else:
            # Check for insect patterns
            for pattern in insect_patterns:
                if re.search(pattern, original_target, re.IGNORECASE):
                    target_type = 'Insect'
                    # Simplify common insect names
                    if 'aphid' in original_target:
                        simplified_target = 'Aphids'
                    elif 'beetle' in original_target:
                        simplified_target = 'Beetles'
                    elif 'moth' in original_target or 'caterpillar' in original_target:
                        simplified_target = 'Caterpillars/Moths'
                    elif 'fly' in original_target:
                        simplified_target = 'Flies'
                    elif 'thrip' in original_target:
                        simplified_target = 'Thrips'
                    elif 'mite' in original_target:
                        simplified_target = 'Mites'
                    elif 'whitefly' in original_target:
                        simplified_target = 'Whiteflies'
                    elif 'mealybug' in original_target:
                        simplified_target = 'Mealybugs'
                    elif 'leafhopper' in original_target:
                        simplified_target = 'Leafhoppers'
                    elif 'cutworm' in original_target:
                        simplified_target = 'Cutworms'
                    elif 'armyworm' in original_target:
                        simplified_target = 'Armyworms'
                    elif 'leafminer' in original_target:
                        simplified_target = 'Leafminers'
                    elif 'leafroller' in original_target:
                        simplified_target = 'Leafrollers'
                    elif 'mosquito' in original_target:
                        simplified_target = 'Mosquitoes'
                    break
            
            # Check for disease patterns
            if target_type == 'Other':
                for pattern in disease_patterns:
                    if re.search(pattern, original_target, re.IGNORECASE):
                        target_type = 'Disease'
                        # Simplify common disease names
                        if 'powdery' in original_target and 'mildew' in original_target:
                            simplified_target = 'Powdery Mildew'
                        elif 'downy' in original_target and 'mildew' in original_target:
                            simplified_target = 'Downy Mildew'
                        elif 'anthracnose' in original_target:
                            simplified_target = 'Anthracnose'
                        elif 'scab' in original_target:
                            simplified_target = 'Scab'
                        elif 'rot' in original_target:
                            simplified_target = 'Rot Diseases'
                        elif 'blight' in original_target:
                            simplified_target = 'Blight'
                        elif 'spot' in original_target:
                            simplified_target = 'Leaf Spot'
                        elif 'rust' in original_target:
                            simplified_target = 'Rust'
                        break
            
            # Check for weed patterns
            if target_type == 'Other':
                for pattern in weed_patterns:
                    if re.search(pattern, original_target, re.IGNORECASE):
                        target_type = 'Weed'
                        # Simplify common weed names
                        if 'broadleaf' in original_target and 'weed' in original_target:
                            simplified_target = 'Broadleaf Weeds'
                        elif 'annual' in original_target and 'grass' in original_target:
                            simplified_target = 'Annual Grasses'
                        elif 'perennial' in original_target and 'grass' in original_target:
                            simplified_target = 'Perennial Grasses'
                        elif 'annual' in original_target and 'weed' in original_target:
                            simplified_target = 'Annual Weeds'
                        elif 'perennial' in original_target and 'weed' in original_target:
                            simplified_target = 'Perennial Weeds'
                        elif 'weed' in original_target:
                            simplified_target = 'Weeds'
                        elif 'grass' in original_target:
                            simplified_target = 'Grasses'
                        break
            
            # Check for vertebrate patterns
            if target_type == 'Other':
                for pattern in vertebrate_patterns:
                    if re.search(pattern, original_target, re.IGNORECASE):
                        target_type = 'Vertebrate'
                        # Simplify common vertebrate names
                        if 'rodent' in original_target:
                            simplified_target = 'Rodents'
                        elif 'mouse' in original_target or 'rat' in original_target:
                            simplified_target = 'Rats/Mice'
                        elif 'bird' in original_target:
                            simplified_target = 'Birds'
                        elif 'deer' in original_target:
                            simplified_target = 'Deer'
                        elif 'rabbit' in original_target:
                            simplified_target = 'Rabbits'
                        break
        
        # Store the suggestions
        original_key = str(original_target_raw) if not pd.isna(original_target_raw) else 'N/A'
        suggested_mapping[original_key] = simplified_target
        target_type_mapping[original_key] = target_type
    
    # Apply the suggestions to the dataframe
    df['Suggested_Simplified_Target'] = df['Original_Target'].map(suggested_mapping)
    df['Target_Type'] = df['Original_Target'].map(target_type_mapping)
    
    # Add notes for special cases
    df.loc[df['Original_Target'] == 'N/A', 'Notes'] = 'No specific target'
    df.loc[df['Target_Type'] == 'Other', 'Notes'] = 'Review needed - unclear target type'
    
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
