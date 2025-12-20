# Post-Extraction JSON Enhancement Script
# This script takes the raw JSON files from AI extraction and enhances them with additional data
# from EPA databases, including better active ingredients, modes of action, and company information

# Import necessary libraries for data processing and file operations
from openai import OpenAI
from pydantic import BaseModel
from key import *
import json
import os
from rapidfuzz import process, fuzz  # For fuzzy string matching
import pandas as pd  # For data manipulation
import re  # For regular expressions

# Define input and output directories
# Input: Raw JSON files from AI extraction
# Output: Enhanced JSON files with additional EPA data
input_folder = "../pipeline_critical_docs/output_json"
output_folder = "../pipeline_critical_docs/altered_json"

# Load the EPA data dump CSV file that contains registration information
# This file was created during the main pipeline processing
ais_df = pd.read_csv("../pipeline_critical_docs/ais_lookup.csv")

# Load the mode of action lookup table
# This Excel file contains information about how different active ingredients work
mode_of_action_df = pd.read_excel("../pipeline_critical_docs/mode_of_action.xlsx")
print(f"Loaded mode of action lookup table with {len(mode_of_action_df)} entries")

# Load the units unification lookup table
# This CSV file contains mappings from various unit formats to standardized units
units_df = pd.read_csv("../pipeline_critical_docs/units_unified.csv")
print(f"Loaded units unification table with {len(units_df)} entries")

# Create a lookup dictionary for active ingredient names to mode of action
# This allows us to quickly find the mode of action for any ingredient
mode_of_action_lookup = {}
for _, row in mode_of_action_df.iterrows():
    ingredient_name = str(row['Active ingredient']).strip().lower()  # Normalize ingredient name
    mode_of_action = str(row['Mode of Action']).strip()  # Get the mode of action
    mode_of_action_lookup[ingredient_name] = mode_of_action  # Store in dictionary

print(f"Created lookup dictionary with {len(mode_of_action_lookup)} entries")

# Create a lookup dictionary for units unification
# This allows us to quickly find the standardized unit for any unit string
units_lookup = {}
for _, row in units_df.iterrows():
    unit_string = str(row['Unit']).strip()  # Original unit string
    unified_unit = str(row['Unified']).strip() if pd.notna(row['Unified']) else ""  # Standardized unit
    units_lookup[unit_string] = unified_unit  # Store in dictionary

print(f"Created units lookup dictionary with {len(units_lookup)} entries")


def unify_units(original_units):
    """
    Unify units based on the units_unified.csv lookup table.
    
    Args:
        original_units (str): Original units string from JSON
    
    Returns:
        str: Unified units string, or original if no match found or unified value is blank
    """
    if not original_units or pd.isna(original_units):
        return original_units
    
    # Clean the input units string
    original_units = str(original_units).strip()
    
    # Look for exact match in the units lookup dictionary
    if original_units in units_lookup:
        unified_unit = units_lookup[original_units]
        # Return unified unit if it's not blank, otherwise return original
        return unified_unit if unified_unit else original_units
    
    # If no exact match found, return the original units
    return original_units


def parse_ais_column(ais_text):
    """
    Parse AIS (Active Ingredient Statement) column text into structured data.
    
    The AIS column contains text like: "Piperonyl butoxide (067501/51-03-6) - (.5%), Pyrethrins (069001/8003-34-7) - (.05%)"
    This function breaks it down into individual ingredients with their codes and percentages.
    
    Args:
        ais_text (str): Raw AIS text from EPA database
    
    Returns:
        list: List of dictionaries with 'name', 'code', 'percentage', and 'mode_of_action' keys
    """
    # Handle empty or missing data
    if pd.isna(ais_text) or ais_text.strip() == '':
        return []
    
    # Clean up the text - remove trailing commas and extra spaces
    ais_text = ais_text.strip().rstrip(',').strip()
    
    # Split by comma to separate individual ingredients
    ingredients = [ing.strip() for ing in ais_text.split(',') if ing.strip()]
    
    parsed_ingredients = []
    
    for ingredient in ingredients:
        # Pattern to match EPA format: "Name (code) - (percentage%)"
        # The regex pattern breaks down as:
        # (.*?) - captures the ingredient name (non-greedy match)
        # \(([^)]+)\) - captures the EPA code in parentheses
        # \s*-\s* - matches the dash separator with optional spaces
        # \(([^)]+)\) - captures the percentage in parentheses
        pattern = r'^(.*?)\s*\(([^)]+)\)\s*-\s*\(([^)]+)\)$'
        
        match = re.match(pattern, ingredient.strip())
        
        if match:
            # Extract the three components from the match
            name = match.group(1).strip()  # Ingredient name
            code = match.group(2).strip()  # EPA code
            percentage = match.group(3).strip()  # Percentage
            
            # Look up mode of action for this ingredient
            mode_of_action = "?"  # Default value if not found
            ingredient_name_lower = name.lower()  # Normalize for comparison
            
            # Try exact match first (most reliable)
            if ingredient_name_lower in mode_of_action_lookup:
                mode_of_action = mode_of_action_lookup[ingredient_name_lower]
            else:
                # Try fuzzy matching if exact match fails
                # This handles slight variations in ingredient names
                best_match = process.extractOne(ingredient_name_lower, mode_of_action_lookup.keys(), scorer=fuzz.token_sort_ratio)
                if best_match and best_match[1] >= 85:  # 85% similarity threshold
                    mode_of_action = mode_of_action_lookup[best_match[0]]
            
            # Add the parsed ingredient to our list
            parsed_ingredients.append({
                'name': name,
                'code': code,
                'percentage': percentage,
                'mode_of_action': mode_of_action
            })
        else:
            # If the pattern doesn't match, add the raw ingredient as a fallback
            # This ensures we don't lose any data even if the format is unexpected
            parsed_ingredients.append({
                'name': ingredient.strip(),
                'code': '?',
                'percentage': '?',
                'mode_of_action': '?'
            })
    
    return parsed_ingredients


def parse_label_names(label_names_text):
    """
    Parse LABEL_NAMES column text into a list of strings.
    
    The LABEL_NAMES column may contain comma-separated label names.
    This function splits them into a clean list of individual label names.
    
    Args:
        label_names_text (str): Raw LABEL_NAMES text from EPA database
    
    Returns:
        list: List of label name strings
    """
    # Handle empty or missing data
    if pd.isna(label_names_text) or str(label_names_text).strip() == '' or str(label_names_text).strip().lower() == 'nan':
        return []
    
    # Convert to string and clean up
    label_names_text = str(label_names_text).strip()
    
    # Split by comma and clean up each label name
    label_names = [name.strip() for name in label_names_text.split(',') if name.strip()]
    
    return label_names


def format_first_reg_date(date_value):
    """
    Format FIRST_REG_DT into a consistent date format.
    
    Args:
        date_value: Date value from EPA database (could be various formats)
    
    Returns:
        str: Formatted date string in YYYY-MM-DD format, or "?" if invalid
    """
    # Handle empty or missing data
    if pd.isna(date_value):
        return "?"
    
    try:
        # Try to convert to pandas datetime first
        if isinstance(date_value, str):
            # Handle string dates
            parsed_date = pd.to_datetime(date_value, errors='coerce')
        else:
            # Handle datetime objects
            parsed_date = pd.to_datetime(date_value, errors='coerce')
        
        # If parsing failed, return "?"
        if pd.isna(parsed_date):
            return "?"
        
        # Format as YYYY-MM-DD
        return parsed_date.strftime('%Y-%m-%d')
    
    except Exception:
        return "?"


# ─── STEP 1: PARSE ACTIVE INGREDIENT DATA ─────────────────────────────────
# Parse the AIS column and create AIS_list column
# This converts the raw text into structured data we can use
print("Parsing AIS column...")
ais_df['AIS_list'] = ais_df['AIS'].apply(parse_ais_column)

# Display info about the AIS dataframe for verification
print(f"AIS dataframe shape: {ais_df.shape}")
print(f"Number of unique REG_NUMs: {ais_df['REG_NUM'].nunique()}")
print(f"Number of non-null AIS entries: {ais_df['AIS'].notna().sum()}")

# Save the updated dataframe with parsed AIS_list for future use
ais_df.to_csv("../pipeline_critical_docs/ais_lookup_parsed.csv", index=False)
print(f"Saved parsed AIS data to ../pipeline_critical_docs/ais_lookup_parsed.csv")

# ─── STEP 2: LOAD EPA DATA FOR ENHANCEMENT ───────────────────────────────
# Load the parsed AIS data for use in JSON enhancement
ais_df = pd.read_csv("../pipeline_critical_docs/ais_lookup_parsed.csv")

# Load the full EPA Excel file that contains additional information
# This includes signal words, company names, and alternative brand names
april_df = pd.read_excel("../pipeline_critical_docs/apprildatadump_public.xlsx")

# ─── STEP 3: CREATE LOOKUP DICTIONARIES ──────────────────────────────────
# Create lookup dictionaries for REG_NUM to various fields
# These allow us to quickly find information for any registration number
regnum_to_signal = {
    str(row["REG_NUM"]).strip(): str(row["SIGNAL_WORD"]).strip()
    for _, row in april_df.iterrows()
}

regnum_to_company = {
    str(row["REG_NUM"]).strip(): str(row["COMPANY_NAME"]).strip()
    for _, row in april_df.iterrows()
}

regnum_to_abns = {
    str(row["REG_NUM"]).strip(): str(row["ABNS"]).strip()
    for _, row in april_df.iterrows()
}

# Additional lookup dictionaries for new fields
regnum_to_first_reg_dt = {
    str(row["REG_NUM"]).strip(): row["FIRST_REG_DT"]
    for _, row in april_df.iterrows()
    if pd.notna(row["FIRST_REG_DT"])
}

regnum_to_label_names = {
    str(row["REG_NUM"]).strip(): str(row["LABEL_NAMES"]).strip()
    for _, row in april_df.iterrows()
    if pd.notna(row["LABEL_NAMES"])
}

regnum_to_phys_form = {
    str(row["REG_NUM"]).strip(): str(row["PHYS_FORM"]).strip()
    for _, row in april_df.iterrows()
    if pd.notna(row["PHYS_FORM"])
}

regnum_to_pest_cat = {
    str(row["REG_NUM"]).strip(): str(row["PEST_CAT"]).strip()
    for _, row in april_df.iterrows()
    if pd.notna(row["PEST_CAT"])
}

# ─── STEP 4: SETUP OUTPUT DIRECTORY ───────────────────────────────────────
# Create the output folder if it doesn't exist
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# ─── STEP 5: PROCESS ALL JSON FILES ───────────────────────────────────────
# Get list of all JSON files to process
json_files = [f for f in os.listdir(input_folder) if f.endswith(".json")]
print(f"Processing {len(json_files)} JSON files...")

# Process each JSON file one by one
for i, filename in enumerate(json_files, 1):
    # Set up input and output file paths
    input_path = os.path.join(input_folder, filename)
    output_path = os.path.join(output_folder, filename)
    
    # Load the JSON data from the input file
    with open(input_path, "r") as infile:
        data = json.load(infile)

    # ─── STEP 5A: EXTRACT REGISTRATION NUMBER ─────────────────────────────
    # Get the EPA registration number from the JSON
    # This is the key we use to look up additional information
    epa_reg_no = str(data.get("pesticide", {}).get("epa_reg_no", "")).strip()
    
    # ─── STEP 5B: LOOK UP EPA DATA ───────────────────────────────────────
    # Look up the values from the EPA Excel file using the registration number
    signal_word = regnum_to_signal.get(epa_reg_no, "N/A")  # Get signal word (CAUTION, WARNING, etc.)
    company_name = regnum_to_company.get(epa_reg_no, "N/A")  # Get company name
    abns = regnum_to_abns.get(epa_reg_no, "N/A")  # Get alternative brand names
    
    # Look up new fields
    first_reg_dt_raw = regnum_to_first_reg_dt.get(epa_reg_no)  # Get first registration date
    first_reg_dt = format_first_reg_date(first_reg_dt_raw)  # Format the date
    
    label_names_raw = regnum_to_label_names.get(epa_reg_no, "")  # Get label names
    label_names = parse_label_names(label_names_raw)  # Parse into list
    
    phys_form = regnum_to_phys_form.get(epa_reg_no, "?")  # Get physical form
    
    pest_cat = regnum_to_pest_cat.get(epa_reg_no, "?")  # Get pest category
    
    # ─── STEP 5C: ENHANCE THE JSON DATA ──────────────────────────────────
    # Update the pesticide data with the additional information
    if "pesticide" in data:
        # Replace the AI-extracted CAUTION_statement with the official SIGNAL_WORD from EPA
        data["pesticide"]["CAUTION_statement"] = signal_word
        
        # Add COMPANY_NAME and ABNS (Alternative Brand Names) to the pesticide data
        pesticide_data = data["pesticide"]
        pesticide_data["COMPANY_NAME"] = company_name
        pesticide_data["ABNS"] = abns
        
        # Add new fields to the Safety_Information section
        if "Safety_Information" not in pesticide_data:
            pesticide_data["Safety_Information"] = {}
        
        pesticide_data["Safety_Information"]["FIRST_REG_DT"] = first_reg_dt  # First registration date (formatted)
        pesticide_data["Safety_Information"]["LABEL_NAMES"] = label_names    # List of label names
        pesticide_data["Safety_Information"]["PHYS_FORM"] = phys_form        # Physical form
        pesticide_data["Safety_Information"]["PEST_CAT"] = pest_cat          # Pest category
        
        # ─── STEP 5D: UPDATE ACTIVE INGREDIENTS ───────────────────────────
        # Update Active_Ingredients using the parsed AIS_list from EPA data
        # Find the row in ais_df with REG_NUM matching epa_reg_no
        ais_row = ais_df[ais_df['REG_NUM'].astype(str) == epa_reg_no]
        if not ais_row.empty:
            ais_list = ais_row.iloc[0]['AIS_list']
            
            # Handle case where AIS_list is stored as string in CSV
            if isinstance(ais_list, str):
                try:
                    import ast
                    ais_list = ast.literal_eval(ais_list)
                except (ValueError, SyntaxError):
                    ais_list = []
            
            # Convert to the schema format: list of dicts with 'name', 'mode_Of_Action', and 'percentage'
            new_active_ingredients = []
            if isinstance(ais_list, list) and len(ais_list) > 0:
                for ing in ais_list:
                    # Only add if name is not empty (avoid adding blank ingredients)
                    if ing.get('name', '').strip():
                        new_active_ingredients.append({
                            "name": ing.get('name', ''),
                            "mode_Of_Action": ing.get('mode_of_action', '?'),
                            "percentage": ing.get('percentage', '?')
                        })
                # Only replace if we have at least one ingredient (avoid empty lists)
                if new_active_ingredients:
                    data["pesticide"]["Active_Ingredients"] = new_active_ingredients

        # ─── STEP 5D: UNIFY UNITS IN APPLICATION_INFO ───────────────────
        # Process units in Application_Info array to standardize them
        if "Application_Info" in data["pesticide"] and isinstance(data["pesticide"]["Application_Info"], list):
            for application in data["pesticide"]["Application_Info"]:
                if isinstance(application, dict) and "units" in application:
                    # Unify the units field
                    original_units = application["units"]
                    unified_units = unify_units(original_units)
                    application["units"] = unified_units

    # ─── STEP 5E: SAVE ENHANCED JSON ─────────────────────────────────────
    # Save the enhanced JSON data to the output file
    with open(output_path, "w") as outfile:
        json.dump(data, outfile, indent=4)
    
    if i % 100 == 0:
        print(f"Processed {i}/{len(json_files)} files...")

print("Post-extraction processing complete!")
