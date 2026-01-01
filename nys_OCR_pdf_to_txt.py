#!/usr/bin/env python3
"""
a new script for OCR. This script can follow the following logic:
- if any page in the each_page_len column is less than 300 characters, then do OCR
- if text contains at least one of the product name or epa no, if it does we are confident that the document is the correct one.
- if product type is primary label and it doesnt contain children do OCR
"""
import pandas as pd
import os
import fitz  # pymupdf
import difflib
import ast
import pytesseract
from PIL import Image
import io


def decide_ocr_vs_original(each_page_len_OCR_val, each_page_len_val):
    try:
        # Parse stringified lists to real lists
        ocr_lengths = ast.literal_eval(each_page_len_OCR_val) if isinstance(each_page_len_OCR_val, str) else []
        orig_lengths = ast.literal_eval(each_page_len_val) if isinstance(each_page_len_val, str) else []
        if not (isinstance(ocr_lengths, list) and isinstance(orig_lengths, list)):
            return "Original"
        # Pad lists if they have different lengths
        min_len = min(len(ocr_lengths), len(orig_lengths))
        for i in range(min_len):
            ocr_len = int(ocr_lengths[i])
            print(ocr_len)
            orig_len = int(orig_lengths[i])
            print(orig_len)
            if ocr_len - orig_len > 100:
                return "OCR"
        return "Original"
    except Exception:
        return "exception"




def fuzzy_contains_children(text):
    text_lower = text.lower().replace(" ", "")
    # Consider searching in chunks to handle missing spaces in "keepoutofreachofchildren"
    possible_chunks = [text_lower[i:i+8] for i in range(len(text_lower)-7)]
    matches = difflib.get_close_matches("children", possible_chunks, n=1, cutoff=0.8)
    # Extra: also check for the common misspelling "childern"
    misspelled_chunks = difflib.get_close_matches("childern", possible_chunks, n=1, cutoff=0.8)
    return bool(matches or misspelled_chunks)


def extract_text_with_ocr(pdf_path, idx, page_specific=False):
    """
    Extract text from PDF using fitz, with OCR on pages that need it.
    
    Args:
        pdf_path: Path to the PDF file
        idx: Index for logging purposes
        page_specific: If True, only OCR pages with < 300 chars. If False, OCR all pages.
    
    Returns:
        tuple: (text, page_lengths) where text is the extracted text and page_lengths is a list of character counts per page
    """
    page_lengths = []
    text = ""
    
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            extracted_text = page.get_text() or ""

            # Determine if this page needs OCR
            if page_specific:
                # Only OCR if extracted text is too short
                needs_ocr = len(extracted_text) < 300
            else:
                # Always OCR for full document OCR
                needs_ocr = True

            final_text = extracted_text
            final_len = len(extracted_text)

            if needs_ocr:
                # Render the page as an image at a higher resolution for better OCR accuracy
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(8, 8))
                    img_bytes = pix.tobytes(output="png")
                    img = Image.open(io.BytesIO(img_bytes))
                    ocr_text = pytesseract.image_to_string(img) or ""
                    final_text = ocr_text
                    final_len = len(ocr_text)
                except (Image.DecompressionBombError, MemoryError) as e:
                    print(f"[{idx}] WARNING: High-res image too large on page {page.number + 1}, using lower resolution: {e}")
                    # Retry with lower resolution
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                        img_bytes = pix.tobytes(output="png")
                        img = Image.open(io.BytesIO(img_bytes))
                        ocr_text = pytesseract.image_to_string(img) or ""
                        final_text = ocr_text
                        final_len = len(ocr_text)
                    except (Image.DecompressionBombError, MemoryError) as e2:
                        print(f"[{idx}] ERROR: Even low-res image failed on page {page.number + 1}, skipping OCR for this page: {e2}")
                        # Fall back to original extracted text
                        final_text = extracted_text
                        final_len = len(extracted_text)

            # Bookend each page with highly-identifiable markers so downstream
            # processing can reliably map text spans to PDF pages.
            text += f"\n\n***PAGE {page_num} START***\n\n"
            text += final_text
            text += f"\n\n***PAGE {page_num} END***\n\n"
            page_lengths.append(final_len)
    
    return text, page_lengths


def perform_ocr_quality_checks(text, pdf_filename, product_no, idx, current_products_edited, row):
    """
    Perform quality checks on OCR text: check for product name, children, and EPA number.
    
    Args:
        text: The extracted OCR text
        pdf_filename: Name of the PDF file
        product_no: Product number from the row
        idx: Index for dataframe updates
        current_products_edited: The dataframe to update
        row: The current row being processed
    
    Returns:
        tuple: (txt_contains_product_name, txt_contains_children, txt_contains_epa_no)
    """
    # Extract product keyword from PDF filename
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
    
    # Check if text contains "children" (fuzzy match)
    txt_contains_children = fuzzy_contains_children(text)
    
    # Check if text contains EPA Reg No (from Product No.)
    epa_reg_no = None
    if product_no:
        # epa_reg_no is everything left of the second "-" (or all if less than 2 dashes)
        parts = str(product_no).strip().split("-")
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
    txt_contains_epa_no = False
    if epa_reg_no_clean:
        txt_contains_epa_no = epa_reg_no_clean in text_for_match
    
    # Update dataframe with results
    current_products_edited.at[idx, "OCR_text_contains_product_name"] = txt_contains_product_name
    current_products_edited.at[idx, "OCR_text_contains_children"] = txt_contains_children
    current_products_edited.at[idx, "OCR_text_contains_epa_no"] = txt_contains_epa_no
    
    return txt_contains_product_name, txt_contains_children, txt_contains_epa_no



# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Use nyspad_csv_downloads directory for CSV files
csv_dir = os.path.join(script_dir, "nyspad_csv_downloads")
os.makedirs(csv_dir, exist_ok=True)

# Path to current_products_edited_txt.csv (in nyspad_csv_downloads)
current_products_csv_path = os.path.join(csv_dir, "current_products_edited_txt.csv")
current_products_edited = pd.read_csv(current_products_csv_path)
print("Imported current_products_edited_txt.csv")

# Path to the PDFs directory (relative to script_dir)
pdf_dir = os.path.join(script_dir, "PDFs")
pdf_dir = os.path.abspath(pdf_dir)

# Initialize OCR columns if they don't exist
if "OCR_text_contains_product_name" not in current_products_edited.columns:
    current_products_edited["OCR_text_contains_product_name"] = None
if "OCR_text_contains_children" not in current_products_edited.columns:
    current_products_edited["OCR_text_contains_children"] = None
if "OCR_text_contains_epa_no" not in current_products_edited.columns:
    current_products_edited["OCR_text_contains_epa_no"] = None



for idx, row in current_products_edited.iterrows():
    print(idx)
    pdf_filename = row['pdf_filename'] if 'pdf_filename' in row else None
    if not pdf_filename or not isinstance(pdf_filename, str) or pd.isna(pdf_filename):
        print(f"[{idx}] Skipped (no pdf_filename)")
        current_products_edited.at[idx, "txt_file_len"] = None
        continue

    # Build the full path to the PDF file
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    if os.path.exists(pdf_path):
        print(f"[{idx}] Found PDF: {pdf_filename}")
    else:
        print(f"[{idx}] MISSING PDF: {pdf_filename}")



    # Convert the PDF to a txt file and save it in PDFs/nyspad_label_txt_OCR directory
    txt_dir = os.path.join(script_dir, "PDFs", "nyspad_label_txt_OCR")
    os.makedirs(txt_dir, exist_ok=True)
    txt_filename = pdf_filename.replace(".pdf", "_OCR.txt")
    txt_path = os.path.join(txt_dir, txt_filename)

    # Skip OCR if the txt file already exists
    if os.path.exists(txt_path):
        print(f"[{idx}] TXT already exists, skipping OCR: {txt_path}")
        # Parse the end metadata of the existing OCR txt file to get column values

        # Initialize default values
        ocr_product_name = None
        ocr_children = None
        ocr_epa_no = None
        ocr_needed_status = None
        run_ocr_reason_value = None
        ocr_v_original_value = None
        post_ocr_char_per_page = None
        
        # Initialize columns if they don't exist
        if "Post_OCR_char_per_page" not in current_products_edited.columns:
            current_products_edited["Post_OCR_char_per_page"] = None
        if "OCR_v_Original" not in current_products_edited.columns:
            current_products_edited["OCR_v_Original"] = None
        
        # Read the last ~40 lines of the file and parse key info, INCLUDING Post_OCR_char_per_page
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read all lines (if file is very large, seek near the end)
                f.seek(0, os.SEEK_END)
                size = f.tell()
                seek_size = min(size, 4096)
                f.seek(max(size - seek_size, 0), os.SEEK_SET)
                lines = f.readlines()[-40:]  # Take up to last 40 lines

                # Parse metadata from the end of the file
                for line in reversed(lines):
                    striped = line.strip()
                    # OCR text columns
                    if striped.lower().startswith("ocr_text_contains_product_name:"):
                        ocr_product_name = striped.split(':', 1)[1].strip() or None
                    elif striped.lower().startswith("ocr_text_contains_children:"):
                        ocr_children = striped.split(':', 1)[1].strip() or None
                    elif striped.lower().startswith("ocr_text_contains_epa_no:"):
                        ocr_epa_no = striped.split(':', 1)[1].strip() or None
                    # OCR metadata columns
                    elif striped.lower().startswith("ocr_needed:"):
                        ocr_needed_status = striped.split(':', 1)[1].strip() or None
                    elif striped.lower().startswith("ocr_reason:"):
                        run_ocr_reason_value = striped.split(':', 1)[1].strip() or None
                    elif striped.lower().startswith("ocr_v_original:"):
                        ocr_v_original_value = striped.split(':', 1)[1].strip() or None
                    # Add handling for post OCR char per page
                    elif striped.lower().startswith("post_ocr_char_per_page:"):
                        val = striped.split(':', 1)[1].strip()
                        post_ocr_char_per_page = val if val != "" else None
                
                # Assign all parsed values to dataframe AFTER parsing completes
                current_products_edited.at[idx, "OCR_text_contains_product_name"] = ocr_product_name
                current_products_edited.at[idx, "OCR_text_contains_children"] = ocr_children
                current_products_edited.at[idx, "OCR_text_contains_epa_no"] = ocr_epa_no
                current_products_edited.at[idx, "OCR_needed"] = ocr_needed_status  # Use parsed value, not "TRUE"
                current_products_edited.at[idx, "runOCR_reason"] = run_ocr_reason_value
                current_products_edited.at[idx, "Post_OCR_char_per_page"] = post_ocr_char_per_page
                current_products_edited.at[idx, "OCR_v_Original"] = ocr_v_original_value
                
                print(f"[{idx}] Successfully parsed metadata from existing OCR TXT file")
                
        except Exception as e:
            print(f"[{idx}] Error parsing OCR metadata from TXT: {e}")
            # Set default values on error
            current_products_edited.at[idx, "OCR_needed"] = "TRUE"  # Fallback if parsing fails
            current_products_edited.at[idx, "runOCR_reason"] = "TXT output already exists; skipping OCR"
        
        continue

    

    
    run_OCR = False
    run_OCR_reason = None
    each_page_len_val = row['each_page_len']
    print(f"[{idx}] Raw PDF to TXT char per page: {each_page_len_val}")

    if each_page_len_val:
        try:
            page_lengths = ast.literal_eval(each_page_len_val) if isinstance(each_page_len_val, str) else []
            # Only check if we have a list of page lengths
            if isinstance(page_lengths, list):
                if any(int(l) < 300 for l in page_lengths if isinstance(l, (int, float, str)) and str(l).isdigit()):
                    run_OCR = "Page_specific_OCR"
                    print("at least one page is less than 300 characters, RUNNING OCR")
                    pages_needing_ocr = [i+1 for i, l in enumerate(page_lengths) if isinstance(l, (int, float, str)) and str(l).isdigit() and int(l) < 300]
                    num_pages_ocr = len(pages_needing_ocr)
                    total_pages = len(page_lengths)
                    run_OCR_reason = f"{num_pages_ocr} out of {total_pages} pages need OCR because they are less than 300 characters (pages: {pages_needing_ocr})"
                else:
                    print("no pages are less than 300 characters, checking other qa criteria")
                    # Use .get() with default False to handle missing columns
                    text_contains_product_name = row.get('text_contains_product_name', False)
                    text_contains_epa_no = row.get('text_contains_epa_no', False)
                    text_contains_children = row.get('text_contains_children', False)
                    
                    if not text_contains_product_name and not text_contains_epa_no:
                        run_OCR = "Full_document_OCR"
                        print("text doesn't contain product name or epa no, RUNNING OCR")
                        run_OCR_reason = "text doesn't contain product name or epa no"
                    else:
                        print("text contains product name or epa no, not running OCR")
                        if row.get('Auth Type') == 'primary label' and not text_contains_children:
                            run_OCR = "Full_document_OCR"
                            print("text is a primary label and doesn't contain children, RUNNING OCR")
                            run_OCR_reason = "primary label doesn't contain children"
        except Exception as e:
            print(f"[{idx}] Error processing each_page_len or checking QA criteria: {e}")
            import traceback
            traceback.print_exc()
    
    current_products_edited.at[idx, "OCR_needed"] = run_OCR
    current_products_edited.at[idx, "runOCR_reason"] = run_OCR_reason
    if run_OCR:
        if run_OCR == "Page_specific_OCR":
            pre_OCR_char_per_page = each_page_len_val
            print(f"[{idx}] Pre-OCR char per page: {pre_OCR_char_per_page}")
            print(f"[{idx}] Extracting TXT: {txt_path}")
            try:
                # Get pre-OCR quality check values from original text
                pre_txt_contains_product_name = row.get('text_contains_product_name', False)
                pre_txt_contains_children = row.get('text_contains_children', False)
                pre_txt_contains_epa_no = row.get('text_contains_epa_no', False)
                
                # Extract text with page-specific OCR (only pages < 300 chars)
                text, page_lengths = extract_text_with_ocr(pdf_path, idx, page_specific=True)
                post_OCR_char_per_page = page_lengths
                
                # Perform quality checks on OCR text
                product_no = str(row.get("Product No.", "")).strip()
                txt_contains_product_name, txt_contains_children, txt_contains_epa_no = perform_ocr_quality_checks(
                    text, pdf_filename, product_no, idx, current_products_edited, row
                )
                
                # Get current row's original and ocr per-page lengths
                current_products_edited.at[idx, "Post_OCR_char_per_page"] = str(page_lengths)

                ocr_v_orig_result = decide_ocr_vs_original(
                    current_products_edited.at[idx, "Post_OCR_char_per_page"], 
                    current_products_edited.at[idx, "each_page_len"]
                )
                current_products_edited.at[idx, "OCR_v_Original"] = ocr_v_orig_result
                print(ocr_v_orig_result)

                print(f"[{idx}] Post-OCR char per page: {post_OCR_char_per_page}")
                # Concatenate text with post_OCR_char_per_page for record-keeping or further processing
                text = text + "Beyond this point is not pesticide label text, it is OCR metadata." + "\n\n---\nPRE-OCR Details:" + f"\npre-OCR_char_per_page: {pre_OCR_char_per_page}" + f"\n Text contained children: {pre_txt_contains_children}" + f"\n Text contained product name: {pre_txt_contains_product_name}" + f"\n Text contained epa no: {pre_txt_contains_epa_no}" + f"\n OCR_needed: {run_OCR}" + f"\n OCR_reason: {run_OCR_reason}" + "\n\n---\npost OCR details:" + f"\nPost_OCR_char_per_page: {post_OCR_char_per_page}" + f"\nOCR_text_contains_product_name: {txt_contains_product_name}" + f"\nOCR_text_contains_children: {txt_contains_children}" + f"\nOCR_text_contains_epa_no: {txt_contains_epa_no}" + f"\n\n---\nOCR_v_Original: {ocr_v_orig_result}"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"[{idx}] Successfully wrote: {txt_path}")
            except Exception as e:
                print(f"[{idx}] ERROR extracting text from {pdf_path}: {e}")
        #run full document OCR when no children or product name or epa no are found.
        elif run_OCR == "Full_document_OCR":
            print(f"[{idx}] Extracting full OCR TXT: {txt_path}")
            pre_OCR_char_per_page = each_page_len_val
            
            # Get pre-OCR quality check values from original text
            pre_txt_contains_product_name = row.get('text_contains_product_name', False)
            pre_txt_contains_children = row.get('text_contains_children', False)
            pre_txt_contains_epa_no = row.get('text_contains_epa_no', False)
            
            # Extract text with full document OCR (all pages)
            text, page_lengths = extract_text_with_ocr(pdf_path, idx, page_specific=False)
            post_OCR_char_per_page = page_lengths
            
            # Perform quality checks on OCR text
            product_no = str(row.get("Product No.", "")).strip()
            txt_contains_product_name, txt_contains_children, txt_contains_epa_no = perform_ocr_quality_checks(
                text, pdf_filename, product_no, idx, current_products_edited, row
            )
            
            # Store page lengths
            current_products_edited.at[idx, "Post_OCR_char_per_page"] = str(page_lengths)
            
            # Determine OCR vs Original result based on quality checks
            if not txt_contains_product_name and not txt_contains_epa_no:
                ocr_v_orig_result = "text still doesn't contain product name or epa no, manual review required"
            else:
                if row.get('Auth Type') == 'primary label' and not txt_contains_children:
                    ocr_v_orig_result = "primary label still doesn't contain children, manual review required"
                else:
                    ocr_v_orig_result = "OCR"  # OCR was successful
            current_products_edited.at[idx, "OCR_v_Original"] = ocr_v_orig_result
            print(ocr_v_orig_result)
            
            print(f"[{idx}] Post-OCR char per page: {post_OCR_char_per_page}")
            # Concatenate text with metadata for record-keeping
            text = text + "Beyond this point is not pesticide label text, it is OCR metadata." + "\n\n---\nPRE-OCR Details:" + f"\npre-OCR_char_per_page: {pre_OCR_char_per_page}" + f"\n Text contained children: {pre_txt_contains_children}" + f"\n Text contained product name: {pre_txt_contains_product_name}" + f"\n Text contained epa no: {pre_txt_contains_epa_no}" + f"\n OCR_needed: {run_OCR}" + f"\n OCR_reason: {run_OCR_reason}" + "\n\n---\npost OCR details:" + f"\nPost_OCR_char_per_page: {post_OCR_char_per_page}" + f"\nOCR_text_contains_product_name: {txt_contains_product_name}" + f"\nOCR_text_contains_children: {txt_contains_children}" + f"\nOCR_text_contains_epa_no: {txt_contains_epa_no}" + f"\n\n---\nOCR_v_Original: {ocr_v_orig_result}"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[{idx}] Successfully wrote: {txt_path}")

    print("")

# Add final_determination column following instructions

def get_col_safe(row, col):
    """
    Helper to avoid NaN/KeyError and get col value lowercased as string if possible.
    """
    v = row.get(col, "")
    if pd.isna(v):
        return ""
    return str(v).strip()

def bool_or_false(x):
    # helper to interpret bools safely from possibly string/None/nan
    if isinstance(x, bool):
        return x
    if pd.isna(x): return False
    if isinstance(x, str):
        return x.strip().lower() == "true"
    return bool(x)

final_det_values = []
for idx, row in current_products_edited.iterrows():
    ocr_needed = get_col_safe(row, "OCR_needed")
    ocr_v_original = get_col_safe(row, "OCR_v_Original")
    # We need to check both text_contains_product_name and text_contains_epa_no for both original and ocr results
    tc_product_name_val = row.get("text_contains_product_name", False)
    tc_epa_no_val = row.get("text_contains_epa_no", False)
    ocr_tc_product_name = row.get("OCR_text_contains_product_name", False)  # May not exist, default False
    ocr_tc_epa_no = row.get("OCR_text_contains_epa_no", False)              # May not exist, default False

    # Rule 1: If OCR_needed is blank
    if ocr_needed == "":
        final_det = "Original"
    elif ocr_needed == "Page_specific_OCR":
        if ocr_v_original == "Original":
            # If both original columns are False -> Manual_Review
            if not bool_or_false(tc_product_name_val) and not bool_or_false(tc_epa_no_val):
                final_det = "Manual_Review"
            else:
                final_det = "Original"
        elif ocr_v_original == "OCR":
            # If both OCR cols are False -> Manual_Review
            if not bool_or_false(ocr_tc_product_name) and not bool_or_false(ocr_tc_epa_no):
                final_det = "Manual_Review"
            else:
                final_det = "OCR"
        else:
            # fallback
            final_det = ""
    elif ocr_needed == "Full_document_OCR":
        if ocr_v_original == "text still doesn't contain product name or epa no, manual review required":
            final_det = "Manual_Review"
        else:
            final_det = "OCR"
    else:
        # Default (should not be hit)
        final_det = ""
    final_det_values.append(final_det)

current_products_edited["final_determination"] = final_det_values

# Save with the txt_file_len column always included
output_csv_path = os.path.join(csv_dir, "current_products_edited_txt_OCR.csv")
current_products_edited.to_csv(output_csv_path, index=False)
print(f"Saved {output_csv_path}")
# Print total "FALSE" from is_PDF_downloaded, with the text "total pdfs missing"
print("\n\n********SUMMARY OF OCR RESULTS********\n\n")
if "is_PDF_downloaded" in current_products_edited.columns:
    total_missing = (current_products_edited["is_PDF_downloaded"] == False).sum()
    print(f"total pdfs missing: {total_missing}")

# Summarize by final_determination and prompt to delete files for Manual_Review rows

if "final_determination" in current_products_edited.columns:
    counts = current_products_edited["final_determination"].value_counts(dropna=False)
    print("\nSummary of final_determination values:\n")
    for value, count in counts.items():
        print(f"  {value}: {count}")
else:
    print("final_determination column not found!")

# Show filenames for Manual_Review and ask to delete them
if (
    "final_determination" in current_products_edited.columns
    and "pdf_filename" in current_products_edited.columns
):
    manual_review_rows = current_products_edited[current_products_edited["final_determination"] == "Manual_Review"]
    print('\n\n*******PDFs requiring manual review (final_determination = "Manual_Review"):*******\n')
    for fn in manual_review_rows["pdf_filename"]:
        print(fn)

    confirm = input(
        "\n\nDo you want to DELETE the PDF and TXT files for all rows where final_determination == 'Manual_Review'? (type 'yes' to confirm): "
    )
    if confirm.strip().lower() == 'yes':
        for _, row in manual_review_rows.iterrows():
            pdf_filename = row.get("pdf_filename")
            if not pdf_filename or not isinstance(pdf_filename, str):
                continue

            pdf_path = os.path.join(pdf_dir, pdf_filename)
            raw_txt_path = os.path.join(script_dir, "PDFs", "nyspad_label_txt", pdf_filename.replace(".pdf", ".txt"))
            ocr_txt_path = os.path.join(script_dir, "PDFs", "nyspad_label_txt_OCR", pdf_filename.replace(".pdf", "_OCR.txt"))

            files_to_delete = [
                ("PDF", pdf_path),
                ("Raw TXT", raw_txt_path),
                ("OCR TXT", ocr_txt_path)
            ]
            for tag, path in files_to_delete:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        print(f"Deleted {tag}: {path}")
                    else:
                        print(f"{tag} not found (already deleted?): {path}")
                except Exception as e:
                    print(f"Failed to delete {tag} at {path}: {e}")
    else:
        print("Deletion cancelled by user.")

