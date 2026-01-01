#!/usr/bin/env python
"""
Extraction using o4-mini with chat completions API to avoid hanging
"""
from openai import OpenAI
from pydantic import BaseModel
from key import scott_key
import json
import os
from rapidfuzz import process, fuzz
import pandas as pd

# moa_df = pd.read_excel("../pipeline_critical_docs/mode_of_action.xlsx")
# moa_lookup = {
#     raw.casefold(): moa
#     for raw, moa in zip(moa_df["Active ingredient"], moa_df["Mode of Action"])
# }
# lookup_keys = list(moa_lookup)

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


def inference_o4_chat(reg_num, filename, contents, crop_list, output_directory_path):
    """Inference using o4-mini with chat completions API"""
    print("o4-mini chat completions strategy")
    
    # load the output json schema
    with open("schema.json", "r") as file:
        pest_schema = json.load(file)

    # API key
    client = OpenAI(api_key=scott_key)

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
{json.dumps(pest_schema, indent=2)}

LABEL TEXT:
{contents}
"""
    
    # Debug: Check prompt and contents
    print(f"Contents length: {len(contents)} characters")
    print(f"Prompt length: {len(prompt)} characters")
    if len(contents) == 0:
        print("WARNING: Contents is empty!")
    if len(contents) > 200000:  # o4-mini has 200k context window, but we need room for response
        print(f"WARNING: Contents is very large ({len(contents)} chars), may exceed context window!")

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
            max_completion = 32000 if len(contents) > 50000 else 16000
            
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
    
    # # replace the mode of action field with correct mode of action
    # for active_ingredient in response_dict["pesticide"]["Active_Ingredients"]:
    #     name = active_ingredient["name"]
    #     key = name.casefold()
        
    #     moa = moa_lookup.get(key)

    #     # fuzzy match to catch edge cases
    #     if moa is None:
    #         best, score, _ = process.extractOne(name, lookup_keys, scorer=fuzz.WRatio)
    #         if score >= 80:               # threshold you choose
    #             moa = moa_lookup[best]

    #     # if still no match, then set moa to N/A
    #     if not moa or pd.isna(moa) or moa in {"?", "NA"}:
    #         moa = "N/A"
        
    #     active_ingredient["mode_Of_Action"] = moa

    # store the dictionary into a JSON file inside output_json folder as a JSON file
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory_path, exist_ok=True)
    output_path = os.path.join(output_directory_path, filename)
    with open(output_path, "w") as file:
        json.dump(response_dict, file, indent=4)
    return output_path 


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

#filter df to only keep rows where agricultural_use_requirements_and_restricted_entry_interval is "ag" or "rei" or "both"
current_products_edited = current_products_edited[current_products_edited['agricultural_use_requirements_and_restricted_entry_interval'].isin(['ag', 'rei', 'both'])]
print(f"Number of rows in current_products_edited dataframe after filtering: {len(current_products_edited)}")

#set up a loop through each row of current_products_edited dataframe
for idx, row in current_products_edited.iterrows():
    print(idx)
    pdf_filename = row['pdf_filename']
    json_filename = pdf_filename.replace(".pdf", ".json")
    print(pdf_filename)
    if not pdf_filename or not isinstance(pdf_filename, str) or pd.isna(pdf_filename):
        print(f"[{idx}] Skipped (no pdf_filename)")
        continue

    # Build output json file path
    output_json_path = os.path.join("output_json", json_filename)
    if os.path.exists(output_json_path):
        print(f"[{idx}] Skipped (JSON already exists at {output_json_path})")
        current_products_edited.at[idx, "inference_successful"] = False
        continue

    #build full path to txt file, if final_determination is OCR, then use the OCR txt file, if Original or blank, then use the original txt file
    txt_filename = pdf_filename.replace(".pdf", "_OCR.txt") if row['final_determination'] == 'OCR' else pdf_filename.replace(".pdf", ".txt")
    if row['final_determination'] == 'OCR':
        txt_path = os.path.join("PDFs", "nyspad_label_txt_OCR", txt_filename)
    else:
        txt_path = os.path.join("PDFs", "nyspad_label_txt", txt_filename)
    if os.path.exists(txt_path):
        print(f"[{idx}] Found TXT: {txt_path}")
    else:
        print(f"[{idx}] MISSING TXT: {txt_path}")
        continue

    #read the txt file
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    print(f"[{idx}] Text file length: {len(text)} characters")
    if len(text) == 0:
        print(f"[{idx}] WARNING: Text file is empty!")
        continue

    #call the inference_o4_chat function
    inference_o4_chat(row['Product No.'], json_filename, text, crop_list, "output_json")

    #add column to current_products_edited dataframe to indicate if the inference was successful
    current_products_edited.at[idx, "inference_successful"] = True

# Save the current_products_edited dataframe to a csv file
output_csv_path = os.path.join(csv_dir, "current_products_edited_txt_OCR_ag_rei_gpt_query.csv")
current_products_edited.to_csv(output_csv_path, index=False)
print(f"Saved {output_csv_path}")