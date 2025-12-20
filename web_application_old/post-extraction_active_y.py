from openai import OpenAI
from pydantic import BaseModel
from key import *
import json
import os
from rapidfuzz import process, fuzz
import pandas as pd
import re


input_folder = "../pipeline_critical_docs/output_json"
output_folder = "../pipeline_critical_docs/altered_json"

# Load the Excel file and create a dataframe with REG_NUM and AIS columns
#april_df_full = pd.read_excel("apprildatadump_public.xlsx")
#april_df_filtered = april_df_full[
#    (april_df_full["REG_TYPE"] == "Sec3") &
#    (april_df_full["STATUS_GROUP"] == "Active") &
#    (april_df_full["USE_TYPE"] == "End Use")
#].copy()
#ais_df = april_df_filtered[["REG_NUM", "AIS"]].copy()
#print("debug working!")

#ais_df.to_csv("ais_lookup.csv", index=False)
ais_df = pd.read_csv("../pipeline_critical_docs/ais_lookup.csv")

# Load the mode of action lookup table
mode_of_action_df = pd.read_excel("../pipeline_critical_docs/mode_of_action.xlsx")
print(f"Loaded mode of action lookup table with {len(mode_of_action_df)} entries")

# Create a lookup dictionary for active ingredient names to mode of action
mode_of_action_lookup = {}
for _, row in mode_of_action_df.iterrows():
    ingredient_name = str(row['Active ingredient']).strip().lower()
    mode_of_action = str(row['Mode of Action']).strip()
    mode_of_action_lookup[ingredient_name] = mode_of_action

print(f"Created lookup dictionary with {len(mode_of_action_lookup)} entries")


def parse_ais_column(ais_text):
    """
    Parse AIS column text into a list of active ingredients.
    
    Args:
        ais_text (str): Text like "Piperonyl butoxide (067501/51-03-6) - (.5%), Pyrethrins (069001/8003-34-7) - (.05%)"
    
    Returns:
        list: List of dictionaries with 'name', 'code', 'percentage', and 'mode_of_action' keys
    """
    if pd.isna(ais_text) or ais_text.strip() == '':
        return []
    
    # Clean up the text - remove trailing commas and spaces
    ais_text = ais_text.strip().rstrip(',').strip()
    
    # Split by comma to separate individual ingredients
    ingredients = [ing.strip() for ing in ais_text.split(',') if ing.strip()]
    
    parsed_ingredients = []
    
    for ingredient in ingredients:
        # Pattern to match: "Name (code) - (percentage%)"
        # The regex pattern:
        # (.*?) - captures the ingredient name (non-greedy)
        # \(([^)]+)\) - captures the code in parentheses
        # \s*-\s* - matches the dash with optional spaces
        # \(([^)]+)\) - captures the percentage in parentheses
        pattern = r'^(.*?)\s*\(([^)]+)\)\s*-\s*\(([^)]+)\)$'
        
        match = re.match(pattern, ingredient.strip())
        
        if match:
            name = match.group(1).strip()
            code = match.group(2).strip()
            percentage = match.group(3).strip()
            
            # Look up mode of action for this ingredient
            mode_of_action = "?"
            ingredient_name_lower = name.lower()
            
            # Try exact match first
            if ingredient_name_lower in mode_of_action_lookup:
                mode_of_action = mode_of_action_lookup[ingredient_name_lower]
            else:
                # Try fuzzy matching if exact match fails
                best_match = process.extractOne(ingredient_name_lower, mode_of_action_lookup.keys(), scorer=fuzz.token_sort_ratio)
                if best_match and best_match[1] >= 85:  # 85% similarity threshold
                    mode_of_action = mode_of_action_lookup[best_match[0]]
            
            parsed_ingredients.append({
                'name': name,
                'code': code,
                'percentage': percentage,
                'mode_of_action': mode_of_action
            })
        else:
            # If the pattern doesn't match, add the raw ingredient as a fallback
            parsed_ingredients.append({
                'name': ingredient.strip(),
                'code': '?',
                'percentage': '?',
                'mode_of_action': '?'
            })
    
    return parsed_ingredients


# Parse the AIS column and create AIS_list column
print("Parsing AIS column...")
ais_df['AIS_list'] = ais_df['AIS'].apply(parse_ais_column)

# Display info about the AIS dataframe
print(f"AIS dataframe shape: {ais_df.shape}")
print(f"Sample AIS data:")
print(ais_df.head(10))
print(f"Number of unique REG_NUMs: {ais_df['REG_NUM'].nunique()}")
print(f"Number of non-null AIS entries: {ais_df['AIS'].notna().sum()}")

# Show some examples of parsed AIS_list with mode of action
print(f"\nSample parsed AIS_list with mode of action:")
for i, row in ais_df.head(10).iterrows():
    if pd.notna(row['AIS']):
        print(f"REG_NUM: {row['REG_NUM']}")
        print(f"Original AIS: {row['AIS']}")
        print(f"Parsed AIS_list: {row['AIS_list']}")
        print("-" * 50)

# Save the updated dataframe with parsed AIS_list
ais_df.to_csv("../pipeline_critical_docs/ais_lookup_parsed.csv", index=False)
print(f"\nSaved parsed AIS data to ../pipeline_critical_docs/ais_lookup_parsed.csv")

# Print some statistics about mode of action matching
print(f"\nMode of Action Matching Statistics:")
total_ingredients = 0
matched_ingredients = 0

for _, row in ais_df.iterrows():
    if isinstance(row['AIS_list'], list):  # Check if it's a list
        for ingredient in row['AIS_list']:
            total_ingredients += 1
            if ingredient['mode_of_action'] != '?':
                matched_ingredients += 1

print(f"Total ingredients processed: {total_ingredients}")
print(f"Ingredients with mode of action found: {matched_ingredients}")
if total_ingredients > 0:
    print(f"Match rate: {matched_ingredients/total_ingredients*100:.1f}%")

# Show some examples of successful matches
print(f"\nExamples of successful mode of action matches:")
match_count = 0
for _, row in ais_df.iterrows():
    if isinstance(row['AIS_list'], list):
        for ingredient in row['AIS_list']:
            if ingredient['mode_of_action'] != '?':
                print(f"Ingredient: {ingredient['name']} -> Mode of Action: {ingredient['mode_of_action']}")
                match_count += 1
                if match_count >= 10:  # Show first 10 matches
                    break
    if match_count >= 10:
        break

if match_count == 0:
    print("No matches found. This might indicate a naming mismatch between the datasets.")


