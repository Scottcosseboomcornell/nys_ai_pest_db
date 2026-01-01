#!/usr/bin/env python
"""
Parallelized GPT query extraction using o4-mini with chat completions API.
Uses multiprocessing to process multiple labels concurrently.

Optimizations:
- Multiprocessing: Processes multiple labels in parallel
- Progress tracking: Shows progress bar and timing statistics
- Error handling: Errors in one label don't stop others
- Rate limiting: Configurable number of workers to avoid API rate limits
"""
from openai import OpenAI
from pydantic import BaseModel
from key import scott_key
import json
import os
from rapidfuzz import process, fuzz
import pandas as pd
from multiprocessing import Pool, cpu_count
import time
import traceback

# Try to import tqdm for progress bar, but make it optional
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: Install 'tqdm' for progress bars: pip install tqdm")

crop_list = [
    "corn",
    "alfalfa",
    "soybeans",
    "apples",
    "grapes",
    "wheat",
    "potatoes",
    "cabbage",
    "snap beans",
    "dry beans",
    "onions",
    "tomatoes",
    "squash",
    "pumpkins",
    "strawberries",
    "blueberries"]


# o4-mini context window guardrails
O4_MINI_CONTEXT_WINDOW_TOKENS = 200_000
# Rough heuristic; sufficient to avoid obviously-too-large prompts
CHARS_PER_TOKEN_ESTIMATE = 4


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _is_context_length_exceeded_error(exc: Exception) -> bool:
    """
    Best-effort detection for OpenAI 'context_length_exceeded' / max context errors.
    Works across SDK versions by inspecting stringified exception content.
    """
    msg = (str(exc) or "").lower()
    return ("context_length_exceeded" in msg) or ("maximum context length" in msg)


def inference_o4_chat(reg_num, filename, contents, crop_list, output_directory_path):
    """Inference using o4-mini with chat completions API"""
    print("o4-mini chat completions strategy")
    
    # load the output json schema
    with open("schema.json", "r") as file:
        pest_schema = json.load(file)

    # API key
    client = OpenAI(api_key=scott_key)

    # Trim anything after the known "not label text" marker to reduce prompt size
    marker = "Beyond this point is not pesticide label text"
    if isinstance(contents, str) and marker in contents:
        contents = contents.split(marker, 1)[0]

    # Compact schema serialization to reduce tokens (no indentation/whitespace)
    schema_str = json.dumps(pest_schema, separators=(",", ":"))

    prompt = f"""
You are given the OCR/text-extracted content of a pesticide label plus a JSON schema to fill out.

IMPORTANT ABOUT PAGE NUMBERS:
- The label text is divided into explicit page blocks using markers:
  - ***PAGE N START*** (beginning of page N)
  - ***PAGE N END***   (end of page N)
- CRITICAL RULE: If the evidence text you used appears BETWEEN ***PAGE N START*** and ***PAGE N END***, then the correct page number is N.
  - Do NOT subtract 1.
  - Example:
    "***PAGE 3 START*** ... REI is 12 hours ... ***PAGE 3 END***"
    - REI page = 3
- If you cannot confidently determine a page number for a field, use null for the page field (do NOT use "N/A" for page fields).

IMPORTANT ABOUT METADATA:
- Ignore everything after the line: "Beyond this point is not pesticide label text"

Crop List (ONLY include these crops in Application_Info.Target_Crop):
{", ".join(crop_list)}

What to extract:
1) Populate pesticide-level fields in the schema, including:
   - pesticide.PPE and pesticide.PPE_page
   - pesticide.Safety_Information (all subfields) and pesticide.Safety_Information.page
   - pesticide.Active_Ingredients
2) Populate pesticide.Application_Info:
   - Extract EVERY distinct application entry for crops in the crop list.
   - Treat each unique combination of (crop + target pest/disease + application method + rate) as a separate Application_Info entry.
   - For each Application_Info entry, also fill these page fields when possible:
     - low_rate_page (page of low_rate evidence)
     - max_product_per_acre_per_season_page
     - REI_page
     - PHI_page
     - Target_Crop[].page (page where that crop appears in the relevant use table/section)
     - Target_Disease_Pest[].page (page where that target appears in the relevant use table/section)

Normalization / rules:
- If a NON-page field isn't mentioned, write "N/A" for that field.
- Only return crop and target-specific data for crops in the crop list.
- Split multiple pests/diseases/groups separated by semicolons or commas into separate Target_Disease_Pest array items.
  Example: "Anthracnose; Blossom blast" →
  [{{"name":"Anthracnose","page":<int|null>}}, {{"name":"Blossom blast","page":<int|null>}}]
- Don't assume information; only use what is present in the label text.
- REI and PHI values shoud be provided in hours or days (e.g. "4 hours" or "12 days") with no other text so that this information can be easily parsed.
- Double-check no extra crops are included.
- Double-check you captured all pests/targets for each included crop entry.

Return ONLY valid JSON that matches this schema (no markdown, no commentary):
{schema_str}

LABEL TEXT:
{contents}
"""
    
    # Debug: Check prompt and contents
    print(f"Contents length: {len(contents)} characters")
    print(f"Prompt length: {len(prompt)} characters")
    if len(contents) == 0:
        print("WARNING: Contents is empty!")

    # Pre-check: skip obviously-too-large prompts before calling the API
    prompt_tokens_est = _estimate_tokens(prompt)
    print(f"Estimated prompt tokens: ~{prompt_tokens_est:,}")
    min_completion_budget = 2_000
    if prompt_tokens_est + min_completion_budget >= O4_MINI_CONTEXT_WINDOW_TOKENS:
        print(
            f"SKIP: Prompt too large for context window "
            f"(~{prompt_tokens_est:,} prompt tokens + {min_completion_budget:,} completion budget "
            f">= {O4_MINI_CONTEXT_WINDOW_TOKENS:,})."
        )
        return None

    print("enter o4-mini chat API call now")
    
    # Add retry logic with exponential backoff
    max_retries = 3
    base_delay = 10  # seconds
    
    for attempt in range(max_retries):
        try:
            print(f"API call attempt {attempt + 1}/{max_retries}")
            
            # Use o4-mini with chat completions API
            # For o4-mini, we need to account for reasoning tokens + output tokens
            # Increase max_completion_tokens to allow for both reasoning and actual output
            # With ~32k prompt tokens, we have ~168k remaining in the 200k context window
            # Set to 32k to allow plenty of room for reasoning and output
            # Dynamically bound completion tokens so we don't exceed the model context window
            remaining_tokens_est = O4_MINI_CONTEXT_WINDOW_TOKENS - prompt_tokens_est
            safety_margin = 2_000
            max_completion_cap = max(0, remaining_tokens_est - safety_margin)
            default_completion = 32000 if len(contents) > 50000 else 16000
            max_completion = max(0, min(default_completion, max_completion_cap))
            if max_completion < min_completion_budget:
                print(
                    f"SKIP: Not enough room for completion "
                    f"(estimated remaining={remaining_tokens_est:,}, cap={max_completion_cap:,}, chosen={max_completion:,})."
                )
                return None
            
            completion = client.with_options(timeout=300.0).chat.completions.create(
                model="o4-mini",
                messages=[
                    {"role": "system", "content": "Extract pesticide information from label text and return ONLY valid JSON matching the provided schema. No markdown, no extra keys."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=max_completion,  # Increased to allow for reasoning + output
            )
            
            # Debug: Check the completion structure
            if not completion.choices or len(completion.choices) == 0:
                print(f"Full completion object: {completion}")
                raise ValueError("No choices in API response")
            
            finish_reason = completion.choices[0].finish_reason
            usage = completion.usage
            print(f"Finish reason: {finish_reason}")
            if usage:
                print(f"Token usage: {usage.completion_tokens} completion tokens ({usage.completion_tokens_details.reasoning_tokens if usage.completion_tokens_details else 'N/A'} reasoning, {usage.completion_tokens_details.accepted_prediction_tokens if usage.completion_tokens_details else 'N/A'} output)")
            
            if finish_reason == "length":
                print("WARNING: Response was cut off due to token limit!")
                if usage and usage.completion_tokens_details:
                    if usage.completion_tokens_details.reasoning_tokens == usage.completion_tokens:
                        print("WARNING: All completion tokens were used for reasoning - no output generated!")
            elif finish_reason == "content_filter":
                print("WARNING: Response was filtered by content policy!")
            elif finish_reason != "stop":
                print(f"WARNING: Unexpected finish_reason: {finish_reason}")
            
            # Parse the response
            message = completion.choices[0].message
            print(f"Message object: {message}")
            print(f"Message type: {type(message)}")
            print(f"Message attributes: {dir(message)}")
            
            response_text = message.content
            
            # Check if content is None or empty
            if response_text is None:
                print(f"Full completion object: {completion}")
                print(f"Full message object: {message}")
                raise ValueError("Response content is None - API may have been cut off or failed")
            
            if len(response_text) == 0:
                print(f"Full completion object: {completion}")
                print(f"Full message object: {message}")
                raise ValueError("Response content is empty - API returned no content. Check if model name 'o4-mini' is correct.")
            
            print(f"Response received, length: {len(response_text)} characters")
            
            # Try to extract JSON from the response
            try:
                # Remove markdown code blocks if present (```json ... ``` or ``` ... ```)
                if "```" in response_text:
                    # Find the first ``` and last ```
                    first_backtick = response_text.find("```")
                    if first_backtick != -1:
                        # Check if it's ```json or just ```
                        if response_text[first_backtick:first_backtick+7] == "```json":
                            # Remove ```json from start
                            response_text = response_text[first_backtick+7:]
                        elif response_text[first_backtick:first_backtick+3] == "```":
                            # Remove ``` from start
                            response_text = response_text[first_backtick+3:]
                        # Remove trailing ```
                        last_backtick = response_text.rfind("```")
                        if last_backtick != -1:
                            response_text = response_text[:last_backtick]
                        # Strip whitespace
                        response_text = response_text.strip()
                
                # Look for JSON in the response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = response_text[start_idx:end_idx]
                    response_dict = json.loads(json_str)
                else:
                    print(f"No JSON found in response. Response length: {len(response_text)}")
                    print(f"Response text (first 1000 chars): {response_text[:1000]}")
                    print(f"Response text (last 500 chars): {response_text[-500:]}")
                    raise ValueError("No JSON found in response")
                    
            except json.JSONDecodeError as e:
                print(f"JSON parsing failed: {e}")
                print(f"Response text (first 1000 chars): {response_text[:1000]}")
                print(f"Response text (last 500 chars): {response_text[-500:]}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise e
            
            break  # Success, exit retry loop
            
        except Exception as e:
            # If we hit context-length issues, skip this file immediately (no retries)
            if _is_context_length_exceeded_error(e):
                print(f"SKIP: context length exceeded for {filename}: {e}")
                return None
            print(f"API call attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                print(f"Retrying in {delay} seconds...")
                import time
                time.sleep(delay)
            else:
                print("All API call attempts failed")
                raise e

    # Ensure the response has the expected structure
    if "pesticide" not in response_dict:
        print(f"Warning: Response missing 'pesticide' key. Response keys: {list(response_dict.keys())}")
        # Create a basic structure if missing
        response_dict = {
            "pesticide": {
                "label_url": "",
                "epa_reg_no": reg_num,
                "Active_Ingredients": []
            },
            "safety_information": {},
            "application_info": []
        }
    else:
        # replace the label_url with an empty string or relevant default
        response_dict["pesticide"]["label_url"] = ""
        response_dict["pesticide"]["epa_reg_no"] = reg_num
    
    # store the dictionary into a JSON file inside output_json folder as a JSON file
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory_path, exist_ok=True)
    output_path = os.path.join(output_directory_path, filename)
    with open(output_path, "w") as file:
        json.dump(response_dict, file, indent=4)
    return output_path 


def process_single_row(args):
    """
    Process a single row from the dataframe. This function will be called in parallel.
    
    Args:
        args: tuple of (idx, row_dict, script_dir, crop_list, force_reprocess)
    
    Returns:
        dict: Results dictionary with status and updates for this row
    """
    idx, row_dict, script_dir, crop_list, force_reprocess = args
    
    result = {
        'idx': idx,
        'success': False,
        'error': None,
        'status': None
    }
    
    try:
        pdf_filename = row_dict.get('pdf_filename')
        if not pdf_filename or not isinstance(pdf_filename, str) or pd.isna(pdf_filename):
            result['status'] = 'skipped_no_filename'
            result['success'] = False
            return result

        json_filename = pdf_filename.replace(".pdf", ".json")
        
        # Build output json file path
        output_json_path = os.path.join(script_dir, "output_json", json_filename)
        if os.path.exists(output_json_path) and not force_reprocess:
            result['status'] = 'skipped_exists'
            result['success'] = False
            return result

        # Build full path to txt file
        final_determination = row_dict.get('final_determination', '')
        txt_filename = pdf_filename.replace(".pdf", "_OCR.txt") if final_determination == 'OCR' else pdf_filename.replace(".pdf", ".txt")
        
        if final_determination == 'OCR':
            txt_path = os.path.join(script_dir, "PDFs", "nyspad_label_txt_OCR", txt_filename)
        else:
            txt_path = os.path.join(script_dir, "PDFs", "nyspad_label_txt", txt_filename)
        
        if not os.path.exists(txt_path):
            result['status'] = 'missing_txt'
            result['error'] = f"MISSING TXT: {txt_path}"
            result['success'] = False
            return result

        # Read the txt file
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        if len(text) == 0:
            result['status'] = 'empty_txt'
            result['error'] = "Text file is empty"
            result['success'] = False
            return result

        # Call the inference function
        product_no = row_dict.get('Product No.', '')
        output_path = inference_o4_chat(product_no, json_filename, text, crop_list, os.path.join(script_dir, "output_json"))

        # Skip gracefully when prompt/context is too large
        if output_path is None:
            result['status'] = 'skipped_too_many_tokens'
            result['success'] = False
            return result
        
        result['status'] = 'success'
        result['success'] = True
        result['output_path'] = output_path
        
    except Exception as e:
        result['error'] = f"Error processing {pdf_filename}: {str(e)}"
        result['traceback'] = traceback.format_exc()
        result['status'] = 'error'
        result['success'] = False

    return result


# Main execution
if __name__ == '__main__':
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Use nyspad_csv_downloads directory for CSV files
    csv_dir = os.path.join(script_dir, "nyspad_csv_downloads")
    os.makedirs(csv_dir, exist_ok=True)

    # Import current_products_edited_txt_OCR_ag_rei_check.csv as a dataframe
    csv_path = os.path.join(csv_dir, "current_products_edited_txt_OCR_ag_rei_check.csv")
    current_products_edited = pd.read_csv(csv_path)
    print(f"Imported {csv_path}")
    print(f"Number of rows in current_products_edited dataframe: {len(current_products_edited)}")

    # Prompt user BEFORE filtering
    print(f"\n{'='*60}")
    print(f"DATA PROCESSING OPTIONS")
    print(f"{'='*60}")
    print(f"Dataframe has {len(current_products_edited)} rows.")
    print(f"{'='*60}\n")
    
    while True:
        user_input = input("Process full dataframe? (yes/no): ").strip().lower()
        if user_input in ['yes', 'y']:
            num_rows = len(current_products_edited)
            print(f"Processing all {num_rows} rows.")
            break
        elif user_input in ['no', 'n']:
            while True:
                try:
                    num_rows_input = input(f"How many rows to process? (1-{len(current_products_edited)}): ").strip()
                    num_rows = int(num_rows_input)
                    if 1 <= num_rows <= len(current_products_edited):
                        print(f"Processing first {num_rows} rows.")
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(current_products_edited)}.")
                except ValueError:
                    print("Please enter a valid number.")
            break
        else:
            print("Please enter 'yes' or 'no'.")
    
    # Ask if user wants to force reprocessing of existing files
    print(f"\n{'='*60}")
    force_reprocess = False
    while True:
        force_input = input("Force reprocess existing JSON files? (yes/no, default=no): ").strip().lower()
        if force_input in ['yes', 'y']:
            force_reprocess = True
            print("Will reprocess all rows, even if JSON files already exist.")
            break
        elif force_input in ['no', 'n', '']:
            force_reprocess = False
            print("Will skip rows where JSON files already exist.")
            break
        else:
            print("Please enter 'yes' or 'no'.")

    # Filter df to only keep rows where agricultural_use_requirements_and_restricted_entry_interval is "ag" or "rei" or "both"
    current_products_edited = current_products_edited[current_products_edited['agricultural_use_requirements_and_restricted_entry_interval'].isin(['ag', 'rei', 'both'])]
    print(f"Number of rows after filtering: {len(current_products_edited)}")
    
    # Apply the num_rows limit after filtering
    if num_rows > len(current_products_edited):
        print(f"Warning: Requested {num_rows} rows but only {len(current_products_edited)} rows after filtering. Processing all available rows.")
        num_rows = len(current_products_edited)
    
    # Take only the requested number of rows
    current_products_edited = current_products_edited.head(num_rows)
    print(f"Processing {len(current_products_edited)} rows.\n")

    # Initialize inference_successful column if it doesn't exist
    if "inference_successful" not in current_products_edited.columns:
        current_products_edited["inference_successful"] = False

    # Determine number of worker processes
    # Use fewer workers for API calls to avoid rate limits (max 4 workers recommended)
    num_workers = min(4, cpu_count())
    print(f"{'='*60}")
    print(f"PARALLEL GPT QUERY PROCESSING")
    print(f"{'='*60}")
    print(f"Total rows to process: {len(current_products_edited)}")
    print(f"Using {num_workers} worker processes (CPU cores available: {cpu_count()})")
    print(f"Note: Using fewer workers to avoid API rate limits")
    print(f"{'='*60}\n")
    
    # Convert dataframe rows to dicts for pickling (multiprocessing requirement)
    process_args = []
    for idx, row in current_products_edited.iterrows():
        row_dict = row.to_dict()
        process_args.append((idx, row_dict, script_dir, crop_list, force_reprocess))

    # Process in parallel with progress tracking
    start_time = time.time()
    
    if HAS_TQDM:
        # Use tqdm for progress bar
        with Pool(processes=num_workers) as pool:
            results = list(tqdm(
                pool.imap(process_single_row, process_args),
                total=len(process_args),
                desc="Processing labels",
                unit="label"
            ))
    else:
        # Without tqdm, just use regular map
        print("Processing labels...")
        with Pool(processes=num_workers) as pool:
            results = pool.map(process_single_row, process_args)
    
    elapsed_time = time.time() - start_time
    
    # Print statistics
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total labels processed: {len(results)}")
    print(f"Total time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
    if len(results) > 0:
        print(f"Average time per label: {elapsed_time/len(results):.2f} seconds")
    
    # Count statuses
    status_counts = {}
    success_count = 0
    error_count = 0
    for result in results:
        status = result.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
        if result.get('success'):
            success_count += 1
        if result.get('error'):
            error_count += 1
    
    print(f"\nStatus breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print(f"\n✓ Successful: {success_count}")
    if error_count > 0:
        print(f"⚠ Errors: {error_count}")
    print(f"{'='*60}\n")

    # Apply all updates to dataframe
    print("Updating dataframe with results...")
    for result in results:
        idx = result['idx']
        if result.get('error'):
            # Print errors but don't stop processing
            pdf_filename = current_products_edited.at[idx, 'pdf_filename'] if 'pdf_filename' in current_products_edited.columns else 'unknown'
            print(f"[{idx}] ERROR: {result['error']}")
            if 'traceback' in result:
                print(result['traceback'])
            current_products_edited.at[idx, "inference_successful"] = False
        else:
            current_products_edited.at[idx, "inference_successful"] = result.get('success', False)

    # Save the current_products_edited dataframe to a csv file
    output_csv_path = os.path.join(csv_dir, "current_products_edited_txt_OCR_ag_rei_gpt_query.csv")
    current_products_edited.to_csv(output_csv_path, index=False)
    print(f"\nSaved {output_csv_path}")

