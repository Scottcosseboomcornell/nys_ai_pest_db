#!/usr/bin/env python3
"""
Imports current_products_edited.csv and converts the pdfs to txt files.
Also adds a txt_file_len column (length of each extracted txt file, or None if not found/extracted).
"""
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

# Path to current_products_edited.csv (in nyspad_csv_downloads)
current_products_csv_path = os.path.join(csv_dir, "current_products_edited.csv")
current_products_edited = pd.read_csv(current_products_csv_path)
print("Imported current_products_edited.csv")

# Make sure txt_file_len exists and fill with None to begin with
if "txt_file_len" not in current_products_edited.columns:
    current_products_edited["txt_file_len"] = None

# Make sure each_page_len exists and fill with None to begin with
if "each_page_len" not in current_products_edited.columns:
    current_products_edited["each_page_len"] = None

# Initialize text quality check columns if they don't exist
if "text_contains_product_name" not in current_products_edited.columns:
    current_products_edited["text_contains_product_name"] = None
if "text_contains_children" not in current_products_edited.columns:
    current_products_edited["text_contains_children"] = None
if "text_contains_epa_no" not in current_products_edited.columns:
    current_products_edited["text_contains_epa_no"] = None

# Path to the PDFs directory (relative to script_dir)
pdf_dir = os.path.join(script_dir, "PDFs")
pdf_dir = os.path.abspath(pdf_dir)

for idx, row in current_products_edited.iterrows():
    pdf_filename = row['pdf_filename'] if 'pdf_filename' in row else None
    if not pdf_filename or not isinstance(pdf_filename, str) or pd.isna(pdf_filename):
        print(f"[{idx}] Skipped (no pdf_filename)")
        current_products_edited.at[idx, "txt_file_len"] = None
        continue

    # Build the full path to the PDF file
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    if os.path.exists(pdf_path):
        print(f"[{idx}] Found PDF: {pdf_path}")
    else:
        print(f"[{idx}] MISSING PDF: {pdf_path}")

    # Convert the PDF to a txt file and save it in PDFs/nyspad_label_txt directory
    txt_dir = os.path.join(script_dir, "PDFs", "nyspad_label_txt")
    os.makedirs(txt_dir, exist_ok=True)
    txt_filename = pdf_filename.replace(".pdf", ".txt")
    txt_path = os.path.join(txt_dir, txt_filename)
    txt_file_len = None

    if os.path.exists(txt_path):
        print(f"[{idx}] Found TXT: {txt_path}")
        # Parse metadata from existing txt file to restore column values
        # Initialize default values
        txt_file_len_val = None
        each_page_len_val = None
        text_contains_product_name_val = None
        text_contains_children_val = None
        text_contains_epa_no_val = None
        metadata_found = False
        
        try:
            with open(txt_path, "r", encoding="utf-8", errors='ignore') as f:
                # Read full file content
                full_content = f.read()
                
                # Check if metadata marker exists
                metadata_marker = "Beyond this point is not pesticide label text, it is raw text metadata."
                if metadata_marker in full_content:
                    # Extract text before metadata for accurate length
                    text_before_metadata = full_content.split(metadata_marker)[0]
                    txt_file_len_val = len(text_before_metadata)
                    
                    # Read last ~40 lines for metadata parsing
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    seek_size = min(size, 4096)
                    f.seek(max(size - seek_size, 0), os.SEEK_SET)
                    lines = f.readlines()[-40:]  # Take up to last 40 lines
                    
                    # Parse metadata from the end of the file
                    for line in reversed(lines):
                        striped = line.strip()
                        # Parse metadata fields
                        if striped.lower().startswith("txt_file_len:"):
                            val = striped.split(':', 1)[1].strip()
                            if val.isdigit():
                                txt_file_len_val = int(val)
                        elif striped.lower().startswith("each_page_len:"):
                            val = striped.split(':', 1)[1].strip()
                            each_page_len_val = val if val != "" else None
                        elif striped.lower().startswith("text_contains_product_name:"):
                            val = striped.split(':', 1)[1].strip()
                            text_contains_product_name_val = val.lower() == 'true' if val else None
                        elif striped.lower().startswith("text_contains_chil:"):
                            val = striped.split(':', 1)[1].strip()
                            text_contains_children_val = val.lower() == 'true' if val else None
                        elif striped.lower().startswith("text_contains_epa_no:"):
                            val = striped.split(':', 1)[1].strip()
                            text_contains_epa_no_val = val.lower() == 'true' if val else None
                    
                    # Check if we found all metadata fields
                    if (txt_file_len_val is not None and
                        each_page_len_val is not None and
                        text_contains_product_name_val is not None and
                        text_contains_children_val is not None and
                        text_contains_epa_no_val is not None):
                        metadata_found = True
                else:
                    # Old format file without metadata - calculate length from full content
                    txt_file_len_val = len(full_content)
                
                # Restore values to dataframe if metadata was found
                if metadata_found:
                    current_products_edited.at[idx, "txt_file_len"] = txt_file_len_val
                    current_products_edited.at[idx, "each_page_len"] = each_page_len_val
                    current_products_edited.at[idx, "text_contains_product_name"] = text_contains_product_name_val
                    current_products_edited.at[idx, "text_contains_children"] = text_contains_children_val
                    current_products_edited.at[idx, "text_contains_epa_no"] = text_contains_epa_no_val
                    txt_file_len = txt_file_len_val
                    print(f"[{idx}] Parsed metadata from existing TXT file, skipping extraction")
                else:
                    # File exists but no metadata - will re-extract to add metadata
                    print(f"[{idx}] TXT file exists but no metadata found, will re-extract to add metadata")
                    txt_file_len = None
                
        except Exception as e:
            print(f"[{idx}] Error parsing metadata from TXT file, will re-extract: {e}")
            # If parsing fails, fall through to extraction
            txt_file_len = None
    
    # Extract text if file doesn't exist or metadata parsing failed
    if not os.path.exists(txt_path) or txt_file_len is None:
        if os.path.exists(txt_path):
            print(f"[{idx}] Re-extracting TXT to add metadata: {txt_path}")
        else:
            print(f"[{idx}] Extracting TXT: {txt_path}")
        try:
            page_lengths = []
            with fitz.open(pdf_path) as doc:
                text = ""
                for page in doc:
                    page_text = page.get_text()
                    text += page_text
                    page_lengths.append(len(page_text))
            # This is a quality check to see if the extracted text contains the product name (checks if pdf name matches the actual text and correct label is downloaded). also checks for "children" which is included on every primary label.
            # For "CONCERT_II_100-1347_PRIMARY_LABEL_546508.pdf", take "CONCERT" (before first "_"), search in lower(text).
            product_keyword = None
            if "_" in pdf_filename:
                product_keyword = pdf_filename.split("_")[0].lower()
            else:
                # If there is no "_", just use the whole name before ".pdf"
                product_keyword = pdf_filename.replace(".pdf", "").lower()
            if not product_keyword:
                product_keyword = None
            # Boolean: does the extracted text contain this substring?
            txt_contains_product_name = None
            if product_keyword:
                txt_contains_product_name = product_keyword in text.lower().replace(" ", "")
            else:
                txt_contains_product_name = False
            current_products_edited.at[idx, "text_contains_product_name"] = txt_contains_product_name

            # New column: does text *fuzzily* contain "children" (case-insensitive)?
            # We'll use difflib.get_close_matches for fuzzy matching of "children" and common misspellings
            

            def fuzzy_contains_children(text):
                text_lower = text.lower().replace(" ", "")
                # Consider searching in chunks to handle missing spaces in "keepoutofreachofchildren"
                possible_chunks = [text_lower[i:i+8] for i in range(len(text_lower)-7)]
                matches = difflib.get_close_matches("children", possible_chunks, n=1, cutoff=0.8)
                # Extra: also check for the common misspelling "childern"
                misspelled_chunks = difflib.get_close_matches("childern", possible_chunks, n=1, cutoff=0.8)
                return bool(matches or misspelled_chunks)

            txt_contains_children = fuzzy_contains_children(text)
            current_products_edited.at[idx, "text_contains_children"] = txt_contains_children

            # New Quality Check: Does extracted text contain the EPA Reg No (from Product No.)?
            product_no = str(row.get("Product No.", "")).strip()
            epa_reg_no = None
            if product_no:
                # epa_reg_no is everything left of the second "-" (or all if less than 2 dashes)
                parts = product_no.split("-")
                if len(parts) >= 3:
                    # join first two, e.g. for "100-1347-1671" -> "100-1347"
                    epa_reg_no = "-".join(parts[:2])
                else:
                    epa_reg_no = product_no
            print(epa_reg_no)
            # Remove spaces and make lowercase for matching
            epa_reg_no_clean = epa_reg_no.replace(" ", "").replace("-", "").lower() if epa_reg_no else ""
            print(epa_reg_no_clean)
            text_for_match = text.lower().replace(" ", "").replace("-", "")
            #print(text_for_match)
            txt_contains_epa_no = False
            if epa_reg_no_clean:
                txt_contains_epa_no = epa_reg_no_clean in text_for_match
            current_products_edited.at[idx, "text_contains_epa_no"] = txt_contains_epa_no
            
            # Calculate text length before appending metadata
            text_length_before_metadata = len(text)
            
            # Append metadata to text file before saving
            text = text + "Beyond this point is not pesticide label text, it is raw text metadata." + "\n\n---\nRaw Text Extraction Details:" + f"\ntxt_file_len: {text_length_before_metadata}" + f"\neach_page_len: {str(page_lengths)}" + f"\ntext_contains_product_name: {txt_contains_product_name}" + f"\ntext_contains_chil: {txt_contains_children}" + f"\ntext_contains_epa_no: {txt_contains_epa_no}"
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[{idx}] Successfully wrote: {txt_path}")
            txt_file_len = text_length_before_metadata  # Length before metadata
            current_products_edited.at[idx, "each_page_len"] = str(page_lengths)
        except Exception as e:
            print(f"[{idx}] ERROR extracting text from {pdf_path}: {e}")
            txt_file_len = None
            current_products_edited.at[idx, "each_page_len"] = None

    current_products_edited.at[idx, "txt_file_len"] = txt_file_len

def page_has_text(each_page_len_val):
    try:
        lengths = ast.literal_eval(each_page_len_val) if isinstance(each_page_len_val, str) else []
        if not isinstance(lengths, list):
            return None
        return all(int(l) > 0 for l in lengths)
    except Exception:
        return None

current_products_edited["each_page_has_text"] = current_products_edited["each_page_len"].apply(page_has_text)



# Save with the txt_file_len column always included
output_csv_path = os.path.join(csv_dir, "current_products_edited_txt.csv")
current_products_edited.to_csv(output_csv_path, index=False)
print(f"Saved {output_csv_path}")