# This will check the best text file either the original or the OCR text file
# it will check for both Agricultural Use Requirements and Restricted-entry interval text to filter down the labels to the ones relevant to agriculture

import pandas as pd
import os
import difflib
import fitz  # pymupdf
import ast


# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Use nyspad_csv_downloads directory for CSV files
csv_dir = os.path.join(script_dir, "nyspad_csv_downloads")
os.makedirs(csv_dir, exist_ok=True)

# Path to current_products_edited_txt_OCR.csv (in nyspad_csv_downloads)
current_products_csv_path = os.path.join(csv_dir, "current_products_edited_txt_OCR.csv")

current_products_edited = pd.read_csv(current_products_csv_path)
print("Imported current_products_edited_txt_OCR.csv")
#print number of rows in current_products_edited dataframe
print(f"Number of rows in current_products_edited dataframe: {len(current_products_edited)}")
#filter only ROUTINE in Auth Type column
current_products_edited = current_products_edited[current_products_edited['Auth Type'] == 'ROUTINE']
print(f"Number of rows in current_products_edited dataframe after filtering routine labels: {len(current_products_edited)}")

# Path to the OCRtxt files directory (relative to script_dir)
txt_dir = os.path.join(script_dir, "PDFs", "nyspad_label_txt_OCR")
txt_dir = os.path.abspath(txt_dir)

# Path to the original txt files directory (relative to script_dir)
original_txt_dir = os.path.join(script_dir, "PDFs", "nyspad_label_txt")
original_txt_dir = os.path.abspath(original_txt_dir)

#loop over the rows of the current_products_edited dataframe
for idx, row in current_products_edited.iterrows():
    print(idx)
    pdf_filename = row['pdf_filename'] if 'pdf_filename' in row else None
    print(pdf_filename)
    if not pdf_filename or not isinstance(pdf_filename, str) or pd.isna(pdf_filename):
        print(f"[{idx}] Skipped (no pdf_filename)")
        continue

    # if final_determination is OCR, then check the OCR text file, if Original, then check the original text file
    text = None
    if row['final_determination'] == 'OCR':
        ocr_text_file = os.path.join(txt_dir, pdf_filename.replace(".pdf", "_OCR.txt"))
        if os.path.exists(ocr_text_file):
            with open(ocr_text_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        else:
            print(f"[{idx}] OCR text file not found: {ocr_text_file}")
            continue
    elif row['final_determination'] == 'Original' or (pd.isna(row['final_determination']) or str(row['final_determination']).strip() == ''):
        original_text_file = os.path.join(original_txt_dir, pdf_filename.replace(".pdf", ".txt"))
        if os.path.exists(original_text_file):
            with open(original_text_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        else:
            print(f"[{idx}] Original text file not found: {original_text_file}")
            continue
    else:
        print(f"[{idx}] Unknown final_determination: {row['final_determination']}")
        continue

    # check for both Agricultural Use Requirements and Restricted-entry interval text to filter down the labels to the ones relevant to agriculture using fuzzy matching
    # if the text contains either Agricultural Use Requirements or Restricted-entry interval text, then the label is relevant to agriculture, and a column should be added to the current_products_edited dataframe to indicate this with "ag", "rei" or "both"
    # if the text does not contain either Agricultural Use Requirements or Restricted-entry interval text, then the label is not relevant to agriculture, and a column should be added to the current_products_edited dataframe to indicate this with "none"
    # check the lowercase of the text and search text, substitute spaces with empty string and replace "-" with empty string, then check if the text contains "agricultural use requirements" or "restricted-entry interval" using fuzzy matching
    text_for_match = text.lower().replace(" ", "").replace("-", "")
    search_ag = "agriculturaluserequirements"
    search_rei = "restrictedentryinterval"
    txt_contains_agricultural_use_requirements = search_ag in text_for_match
    txt_contains_restricted_entry_interval = search_rei in text_for_match
    if txt_contains_agricultural_use_requirements and txt_contains_restricted_entry_interval:
        current_products_edited.at[idx, "agricultural_use_requirements_and_restricted_entry_interval"] = "both"
    elif txt_contains_agricultural_use_requirements:
        current_products_edited.at[idx, "agricultural_use_requirements_and_restricted_entry_interval"] = "ag"
    elif txt_contains_restricted_entry_interval:
        current_products_edited.at[idx, "agricultural_use_requirements_and_restricted_entry_interval"] = "rei"
    else:
        current_products_edited.at[idx, "agricultural_use_requirements_and_restricted_entry_interval"] = "none"
    print(current_products_edited.at[idx, "agricultural_use_requirements_and_restricted_entry_interval"])

# Save the current_products_edited dataframe to a csv file
output_csv_path = os.path.join(csv_dir, "current_products_edited_txt_OCR_ag_rei_check.csv")
current_products_edited.to_csv(output_csv_path, index=False)
print(f"Saved {output_csv_path}")

#add summary of the number of rows in the current_products_edited dataframe for each value in the agricultural_use_requirements_and_restricted_entry_interval column
print("\nSummary of agricultural_use_requirements_and_restricted_entry_interval values:")
print(current_products_edited['agricultural_use_requirements_and_restricted_entry_interval'].value_counts(dropna=False))

