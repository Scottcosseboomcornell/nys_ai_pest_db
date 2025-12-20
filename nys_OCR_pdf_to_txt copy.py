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



# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Path to current_products_edited_txt.csv (relative to script_dir)
current_products_csv_path = os.path.join(script_dir, "current_products_edited_txt.csv")
current_products_edited = pd.read_csv(current_products_csv_path)
print("Imported current_products_edited_txt.csv")

# Path to the nyspad_pdfs directory (relative to script_dir)
pdf_dir = os.path.join(script_dir, "..", "..", "pipeline_critical_docs", "nyspad_pdfs")
pdf_dir = os.path.abspath(pdf_dir)

# After line 40 (after loading the CSV), add:
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



    # Convert the PDF to a txt file and save it in nyspad_label_txt_OCR directory
    txt_dir = os.path.join(script_dir, "..", "..", "pipeline_critical_docs", "nyspad_pdfs", "nyspad_label_txt_OCR")
    os.makedirs(txt_dir, exist_ok=True)
    txt_filename = pdf_filename.replace(".pdf", "_OCR.txt")
    txt_path = os.path.join(txt_dir, txt_filename)

    # Skip OCR if the txt file already exists
    if os.path.exists(txt_path):
        print(f"[{idx}] TXT already exists, skipping OCR: {txt_path}")
        current_products_edited.at[idx, "OCR_needed"] = "TRUE" # this is to indicate that OCR was already done, and we are not running it again.
        current_products_edited.at[idx, "runOCR_reason"] = "TXT output already exists; skipping OCR"
        # Parse the end metadata of the existing OCR txt file to get column values

        # Initialize default values
        ocr_product_name = None
        ocr_children = None
        ocr_epa_no = None
        ocr_needed_status = None
        run_ocr_reason_value = None
        ocr_v_original_value = None

        # Read the last ~40 lines of the file and parse key info, INCLUDING Post_OCR_char_per_page
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read all lines (if file is very large, seek near the end)
                f.seek(0, os.SEEK_END)
                size = f.tell()
                seek_size = min(size, 4096)
                f.seek(max(size - seek_size, 0), os.SEEK_SET)
                lines = f.readlines()[-40:]  # Take up to last 40 lines

                # Initialize new value
                post_ocr_char_per_page = None

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
                    # If all found, break early (include new field in check)
                    if (ocr_product_name is not None and
                        ocr_children is not None and
                        ocr_epa_no is not None and
                        ocr_needed_status is not None and
                        run_ocr_reason_value is not None and
                        ocr_v_original_value is not None and
                        post_ocr_char_per_page is not None):
                        break
        except Exception as e:
            print(f"[{idx}] Error parsing OCR metadata from TXT: {e}")
            ocr_product_name = None
            ocr_children = None
            ocr_epa_no = None
            ocr_needed_status = None
            run_ocr_reason_value = None
            ocr_v_original_value = None
            post_ocr_char_per_page = None

        current_products_edited.at[idx, "OCR_text_contains_product_name"] = ocr_product_name
        current_products_edited.at[idx, "OCR_text_contains_children"] = ocr_children
        current_products_edited.at[idx, "OCR_text_contains_epa_no"] = ocr_epa_no
        current_products_edited.at[idx, "OCR_needed"] = ocr_needed_status
        current_products_edited.at[idx, "runOCR_reason"] = run_ocr_reason_value

        # Make sure the new column exists (add if not)
        if "Post_OCR_char_per_page" not in current_products_edited.columns:
            current_products_edited["Post_OCR_char_per_page"] = None
        current_products_edited.at[idx, "Post_OCR_char_per_page"] = post_ocr_char_per_page
        current_products_edited.at[idx, "OCR_v_Original"] = ocr_v_original_value
        print("")
        continue

    
    run_OCR = False
    run_OCR_reason = None
    each_page_len_val = row.get("each_page_len", None)
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
                    if not row.get('text_contains_product_name', False) and not row.get('text_contains_epa_no', False):
                        run_OCR = "Full_document_OCR"
                        print("text doesn't contain product name or epa no, RUNNING OCR")
                        run_OCR_reason = "text doesn't contain product name or epa no"
                    else:
                        print("text contains product name or epa no, not running OCR")
                        if row.get('Auth Type') == 'primary label' and not row.get('text_contains_children', False):
                            run_OCR = "Full_document_OCR"
                            print("text is a primary label and doesn't contain children, RUNNING OCR")
                            run_OCR_reason = "primary label doesn't contain children"
        except Exception as e:
            print(f"[{idx}] Error decoding each_page_len: {e}")
    
    current_products_edited.at[idx, "OCR_needed"] = run_OCR
    current_products_edited.at[idx, "runOCR_reason"] = run_OCR_reason
    if run_OCR:
        if run_OCR == "Page_specific_OCR":
            pre_OCR_char_per_page = each_page_len_val
            print(f"[{idx}] Pre-OCR char per page: {pre_OCR_char_per_page}")
            print(f"[{idx}] Extracting TXT: {txt_path}")
            try:
                
                page_lengths = []
                with fitz.open(pdf_path) as doc:
                    text = ""
                    for page in doc:
                        page_text = page.get_text()
                        text += page_text
                        if int(len(page_text)) < 300:
                            # If the extracted text is too short, run OCR on this page using pytesseract
                            # Render the page as an image at a higher resolution for better OCR accuracy, 3, 3 is typically good enough but 8,8 is very high definition
                            try:
                                pix = page.get_pixmap(matrix=fitz.Matrix(8, 8))
                                img_bytes = pix.tobytes(output="png")
                                img = Image.open(io.BytesIO(img_bytes))
                                ocr_text = pytesseract.image_to_string(img)
                                # Use OCR text for this page
                                text += ocr_text
                                page_text = ocr_text
                                page_lengths.append(len(ocr_text))
                            except (Image.DecompressionBombError, MemoryError) as e:
                                print(f"[{idx}] WARNING: High-res image too large on page {page.number + 1}, using lower resolution: {e}")
                                # Retry with lower resolution
                                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                                img_bytes = pix.tobytes(output="png")
                                img = Image.open(io.BytesIO(img_bytes))
                                ocr_text = pytesseract.image_to_string(img)
                                # Use OCR text for this page
                                text += ocr_text
                                page_text = ocr_text
                                page_lengths.append(len(ocr_text))
                        else:
                            page_lengths.append(len(page_text))
                post_OCR_char_per_page = page_lengths
                #do qa assessment here
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
                current_products_edited.at[idx, "OCR_text_contains_product_name"] = txt_contains_product_name

                # New column: does text *fuzzily* contain "children" (case-insensitive)?
                # We'll use difflib.get_close_matches for fuzzy matching of "children" and common misspellings

                txt_contains_children = fuzzy_contains_children(text)
                current_products_edited.at[idx, "OCR_text_contains_children"] = txt_contains_children

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
                current_products_edited.at[idx, "OCR_text_contains_epa_no"] = txt_contains_epa_no
                #do another qa assessment here to see if the OCR each_page_len_OCR is more than 100 characters greater than the original each_page_len for any of the pages, if so then the ocr was successful, and set the new column in df "OCR_v_Original" to "OCR", but if not then "Original"
                # Compare OCR character length vs original text character length per page.
                # If OCR page is >100 chars longer than original at any page, mark as "OCR", else "Original"



                # Get current row's original and ocr per-page lengths
                current_products_edited.at[idx, "each_page_len_OCR"] = str(page_lengths)

                ocr_v_orig_result = decide_ocr_vs_original(
                    current_products_edited.at[idx, "each_page_len_OCR"], 
                    current_products_edited.at[idx, "each_page_len"]
                )
                current_products_edited.at[idx, "OCR_v_Original"] = ocr_v_orig_result
                print(ocr_v_orig_result)






                print(f"[{idx}] Post-OCR char per page: {post_OCR_char_per_page}")
                # Concatenate text with post_OCR_char_per_page for record-keeping or further processing
                text = text + "Beyond this point is not pesticide label text, it is OCR metadata." + "\n\n---\nPRE-OCR Details:" + f"\npre-OCR_char_per_page: {each_page_len_val}" + f"\n Text contained children: {txt_contains_children}" + f"\n Text contained product name: {txt_contains_product_name}" + f"\n Text contained epa no: {txt_contains_epa_no}" + f"\n OCR_needed: {run_OCR}" + f"\n OCR_reason: {run_OCR_reason}" + "\n\n---\npost OCR details:" + f"\nPost_OCR_char_per_page: {post_OCR_char_per_page}" + f"\nOCR_text_contains_product_name: {txt_contains_product_name}" + f"\nOCR_text_contains_children: {txt_contains_children}" + f"\nOCR_text_contains_epa_no: {txt_contains_epa_no}" + f"\n\n---\nOCR_v_Original: {ocr_v_orig_result}"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"[{idx}] Successfully wrote: {txt_path}")
            except Exception as e:
                print(f"[{idx}] ERROR extracting text from {pdf_path}: {e}")
        #run full document OCR when no children or product name or epa no are found.
        elif run_OCR == "Full_document_OCR":
            print(f"[{idx}] Extracting full OCR TXT: {txt_path}")
            page_lengths = []
            with fitz.open(pdf_path) as doc:
                text = ""
                for page in doc:
                    page_text = page.get_text()
                    text += page_text

                    # Render the page as an image at a higher resolution for better OCR accuracy, 3, 3 is typically good enough but 8,8 is very high definition
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(8, 8))
                        img_bytes = pix.tobytes(output="png")
                        img = Image.open(io.BytesIO(img_bytes))
                        ocr_text = pytesseract.image_to_string(img)
                        # Use OCR text for this page
                        text += ocr_text
                        page_text = ocr_text
                        page_lengths.append(len(ocr_text))
                    except (Image.DecompressionBombError, MemoryError) as e:
                        print(f"[{idx}] WARNING: High-res image too large on page {page.number + 1}, using lower resolution: {e}")
                        # Retry with lower resolution   
                        try:
                            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                            img_bytes = pix.tobytes(output="png")
                            img = Image.open(io.BytesIO(img_bytes))
                            ocr_text = pytesseract.image_to_string(img)
                            # Use OCR text for this page
                            text += ocr_text
                            page_text = ocr_text
                            page_lengths.append(len(ocr_text))
                        except (Image.DecompressionBombError, MemoryError) as e2:
                            print(f"[{idx}] ERROR: Even low-res image failed on page {page.number + 1}, skipping OCR for this page: {e2}")
                            page_lengths.append(len(page_text))
            txt_contains_children = fuzzy_contains_children(text)
            current_products_edited.at[idx, "OCR_text_contains_children"] = txt_contains_children
            text = text + "Beyond this point is not pesticide label text, it is OCR metadata." + "\n\n---\nPRE-OCR Details:" + f"\npre-OCR_char_per_page: {each_page_len_val}" + f"\n Text contained children: {txt_contains_children}" + f"\n Text contained product name: {txt_contains_product_name}" + f"\n Text contained epa no: {txt_contains_epa_no}" + f"\n OCR_needed: {run_OCR}" + f"\n OCR_reason: {run_OCR_reason}" + "\n\n---\npost OCR details:" + f"\nPost_OCR_char_per_page: {post_OCR_char_per_page}" + f"\nOCR_text_contains_product_name: {txt_contains_product_name}" + f"\nOCR_text_contains_children: {txt_contains_children}" + f"\nOCR_text_contains_epa_no: {txt_contains_epa_no}" + f"\n\n---\nOCR_v_Original: {ocr_v_orig_result}"
            with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)
            print(f"[{idx}] Successfully wrote: {txt_path}")

            post_OCR_char_per_page = page_lengths
            print(f"[{idx}] Post-OCR char per page: {post_OCR_char_per_page}")
            current_products_edited.at[idx, "each_page_len_OCR"] = str(page_lengths)
            #do qa assessment here
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
            current_products_edited.at[idx, "OCR_text_contains_product_name"] = txt_contains_product_name

            # New column: does text *fuzzily* contain "children" (case-insensitive)?
            # We'll use difflib.get_close_matches for fuzzy matching of "children" and common misspellings

            txt_contains_children = fuzzy_contains_children(text)
            current_products_edited.at[idx, "OCR_text_contains_children"] = txt_contains_children

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
            current_products_edited.at[idx, "OCR_text_contains_epa_no"] = txt_contains_epa_no
            #do another qa assessment here to see if the OCR each_page_len_OCR is more than 100 characters greater than the original each_page_len for any of the pages, if so then the ocr was successful, and set the new column in df "OCR_v_Original" to "OCR", but if not then "Original"
            # Compare OCR character length vs original text character length per page.
            # If OCR page is >100 chars longer than original at any page, mark as "OCR", else "Original"



            # Get current row's original and ocr per-page lengths
            current_products_edited.at[idx, "each_page_len_OCR"] = str(page_lengths)
            ### UPDATE THIS make it check not for charater count but for the epa no product name and children if 2ee, if it still fails, then mark as manual review
            if not current_products_edited.at[idx, 'OCR_text_contains_product_name'] and not current_products_edited.at[idx, 'OCR_text_contains_epa_no']:
                            ocr_v_orig_result = "text still doesn't contain product name or epa no, manual review required"
            else:
                if row['Auth Type'] == 'primary label' and not current_products_edited.at[idx, 'OCR_text_contains_children']:                    ocr_v_orig_result = "primary label still doesn't contain children, manual review required"
            current_products_edited.at[idx, "OCR_v_Original"] = ocr_v_orig_result
            print(ocr_v_orig_result)

    print("")


# Save with the txt_file_len column always included
output_csv_path = os.path.join(script_dir, "current_products_edited_txt_OCR.csv")
current_products_edited.to_csv(output_csv_path, index=False)
print(f"Saved {output_csv_path}")


# maybe if the difference in character count from the ocr page and the original page is less than 100 characters the original extraction was correct and we can use it.
#add ocr for the full document exceptions when no children or product name or epa no are found.