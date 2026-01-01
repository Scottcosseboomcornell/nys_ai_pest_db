# NYSPAD Automation Scripts

This folder contains scripts for automating the download of pesticide label PDFs from the New York State Pesticide Administration Database (NYSPAD).

## 🎯 Main Scraper: `nyspad_scraper.py`

The **`nyspad_scraper.py`** is a fully functional Selenium-based web scraper that automates the complete workflow for downloading pesticide labels from NYSPAD. Here's what it does:

### ✅ **Core Functionality**
- **Searches by Product Name** (e.g., "Admire Pro")
- **Handles Dynamic Content** - Dismisses modals, waits for page loads
- **Loops Through All Results** - Processes every product returned from search
- **Extracts Complete Product Information** - Saves detailed product data to text files
- **Downloads Actual PDF Labels** - Gets the most recent label document for each product
- **Robust Modal Management** - Opens product modals, extracts data, closes cleanly

### 🔄 **Complete Workflow**
1. **Search**: Enters product name and searches NYSPAD database
2. **Parse Results**: Identifies all products returned (e.g., 6 products for "Admire Pro")
3. **For Each Product**:
   - Clicks "More" button to open product modal
   - Extracts all product information (EPA reg, type, status, ingredients, etc.)
   - Saves product details to `PRODUCT_NAME_EPA_XXX-XXX_Info.txt`
   - Finds and downloads the most recent label PDF
   - Saves PDF as `PRODUCT_NAME_Label_XXXXXX.pdf`
   - Closes modal and moves to next product

### 📁 **Output Files**
- **PDF Labels**: `ADMIRE_PRO_PRODUCT_1_Label_589380.pdf`
- **Product Info**: `ADMIRE_PRO_PRODUCT_1_EPA_264-827_Info.txt`

### 🛠 **Technical Features**
- **Selenium WebDriver** with Chrome browser automation
- **JavaScript execution** to bypass element interaction issues
- **Multiple fallback strategies** for element selection and modal closing
- **Robust error handling** and logging
- **Configurable delays** and headless/visible modes

## Files Overview

- **`nyspad_scraper.py`** - ⭐ **Main scraper** - Complete automation solution
- **`nyspad_data_parser.py`** - Parser for NYSPAD downloadable data files
- **`nyspad_integration.py`** - Integration script that combines all approaches
- **`nyspad_requirements.txt`** - Additional Python dependencies needed
- **`NYSPAD_AUTOMATION_README.md`** - Comprehensive documentation

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r nyspad_requirements.txt
   ```

2. **Run the main scraper** (recommended):
   ```bash
   python nyspad_scraper.py
   ```
   This will search for "Admire Pro" and download all 6 product labels with information files.

3. Or try the NYSPAD data parser:
   ```bash
   python nyspad_data_parser.py
   ```

4. Or use the integrated approach:
   ```bash
   python nyspad_integration.py
   ```

## 🚀 **Recommended Approach**

**Use `nyspad_scraper.py`** - It's the most complete and reliable solution that:
- ✅ Handles all dynamic content automatically
- ✅ Downloads actual PDF labels (not HTML pages)
- ✅ Extracts complete product information
- ✅ Processes multiple products in one run
- ✅ Has robust error handling and modal management

## 📋 **Example Output**

When you run the scraper for "Admire Pro", you'll get:
- **6 PDF files**: Different label documents for each product variant
- **6 Info files**: Complete product details including EPA registration, ingredients, restrictions, etc.
- **Console output**: Real-time progress showing each product being processed

See `NYSPAD_AUTOMATION_README.md` for detailed documentation and examples.


12/4/25
I have gotten the NY scraping script to sucessfully scrape and download the label pdfs for every potentially relevant product that will feed into the AI-json pipeline.


#####################################################################################################################################
This is how it works. first run 
`main_pipeline_scripts/NY_scraping/download_registered_products.py`
this scrapes the file from NYSPAD that contains the current list of products `main_pipeline_scripts/NY_scraping/current_products.csv`
It then looks in
`pipeline_critical_docs/nyspad_pdfs`
which is where the label pdfs are stored and checks to see which pesticides that i dont yet have a pdf for. This folder also contains txt files which contain metadata from the modal view of the pesticide from the nyspad. it saves the results of this characterization of whether the files are in the folder in current_products_edited.csv, which can be a good resource for troubleshooting

It also:
- Gets formulation type from latest DEC_ProductData csv file, it will be appended with the date: `old/Dec_ProductData-2025-12-04-06-46-47.csv`. Get "Formulation" column data where S is Solid, L is Liquid. Also get "LONG ISLAND USE RESTRICTION" where "N" is FALSE and "Y" is TRUE. also get "PRODUCT ID" data. Do this by doing a lookup on the "Product No." column form the main csv, matching to "EPA REGISTRATION NUMBER" column in the DEC_ProductData csv file to retrieve the correct data from the three columns. 

- Gets toxicity from "TOXICITY" column which will can have multiple rows of toxicity for each type of toxicity. make this into a comma separated list for each product ID. do a lookup based on "PRODUCT_ID" from the previous bullet point. this is the file, but get the most recent version `old/Dec_ProductData_Toxicity-2025-12-15-06-46-13.csv`

-It filters: from latest version of `nyspad_csv_downloads/Dec_ProductData_ProductUse-*.csv` it has "PRODUCT ID" that"PRODUCT USE" for each "PRODUCT ID" these can be added as a comma separated list to the original current products edited dataframe and then used to filter the dataframe further to only keep: 
AGRICULTURAL
TURF
NURSERY
ORNAMENTAL
COMMERCIAL
GREENHOUSE
HEMP
CANNABIS
HEMP (EPA LABEL)
SEED TREATMENT

- It also filters according to product type

#####################################################################################################################################
Then from NY_scraping venv, run `python3 new_NY_scraper_search.py --headless=True --max-workers=8 --start-delay=7.0` in the terminal

This runs the new_NY_scraper_search.py, which searches through NYDEC website and downloads the label pdfs and the txt files. it will only search and download the ones that are missing according to current_products_edited.csv. A few tings to note from this script and this command:
- It opens a browser that is hidden if headless = TRUE, but can be visible if headless = false
- it opens simultaneous browsers accourding to the max-workers number. you may want to keep it at 6 or so if you dont want to crash their website or be rude to other users or draw too much attention to the scraping
- it will wait 7 seconds between each time it opens a new simultanrous browser, this can also be edited to be more or less curteous/aggressive
- when it searches for the pesticide, it does this jsut like a person would navigate the website. It searches then opens the nyspad pesticide info using the "more" button, then clicks on the first pesticide label in the list (which should be the most recent). it downloads the file then appends it with the registration number (similar to epa reg no, but can have a two "-"), product name, and label version number (6 digit code)
         - one area for improvement is that it just downloads the first one in the table, which is fine for most, but doesnt take in to consideration that some might be not a full label. and it names them all with "PRIMARY_LABEL" which is not accurate, as some are 2EE or SLN or supplemental labels while most are actually the "PRIMARY LABEL"

#####################################################################################################################################
After all this, you can optionally rerun
`download_registered_products.py`
to get a new count of which products still need to be downloaded.


Now that the PDFs are downloaded, another script: `ny_pdf_to_txt.py` handles extracting the text using a simple text extraction. This script also looks for a number of potential quality control issues and adds new columns to the file `current_products_edited_txt.csv` that can help with QA and troubleshooting:
- `txt_file_len` is the length in number of characters of the txt file. 0 characters indicates the pdf is either corrupted or is a purely scanned pdf. less than 200 indicates that it is scanned except for the overlay text from NY DEC for the approval text. 2EE are expected to be shorter than standard labels but should have at least 500 characters. if txt is too short, then ocr is likely needed.
- `text_contains_product_name` this looks for the first word of the product name like "Miravis" from "Miravis Ace" in the txt. if the txt doesnt contain the product name, this indicates that the actual pdf doent match what we thoght it did, like it could be a label for a different pesticide. Or that the label is partially scanned and needs OCR, however sometimes the product name is a graphical image, so this might not be the most accurate qa for triggering OCR
- `text_contains_children` this looks for the word "children" which is on every primary label in "keep out of reach of children". I have run into labels in the past that mispell children as childern, so be careful. also using a FUZZY MATCH to SOLVE THESE SLIGHT SPELLING ISSUES, with 0.8 match so allowing for 1 mismatched character
- `text_contains_epa_no` this is a qa simlar to text contains product name to ensure that the correct label was downloaded and is likely more reliable than the product name. I think a good qa step would be to check whether eitehr this or product name is true.
- `each_page_len`	: this is the character count per page. if only one page has text and others dont, it is an indicator that some pages are scanned. its expected taht each page should have at least one character
- `each_page_has_text`: this is just a simple true or false for checking if each individual page len is > 0. if one page has no characters it will false.


#####################################################################################################################################
Here is a good time to make a new script for OCR and can follow the following logic:
- if any page (txt_file_len) is less than 300 characters, then do OCR
- if text doesn't contain product name or epa no, then do OCR, if it does we are confident that the document is the correct one.
- if product type is primary label and it doesnt contain children do OCR

I made a script to do OCR when needed `nys_OCR_pdf_to_txt.py`. 
Also made a parrallelized version that is MUCH quicker for doing many at once `nys_OCR_pdf_to_txt_parallel.py`
- It checks the QA columns from the csv from the previous script and runs ocr only on necessary pages, like if they have less than 300 characters.
         - after running, it does the qa again, and then determines if it actually improved the outcome
- then if they are missing product no, product name, or children, it runs ocr on the full document
         - after running it does the qa again and then determiens if it improved the outcome and whether to use the OCR text, the original text, or if the qa indicates that something is really wrong, and manual review is needed. 
                  - i did this on the first 2000 documents  and the OCR was triggered for:  549 documnents (27%). it was determined to be not necessary for 366 of them, improved 170 of them, and 13 (0.5%) needed manual review. most were page specific OCR (532/549), where certain pages seemed to have less than 300 characters. the 13 that needed manual review turned out to be the wrong PDF, where something went wrong during the scraping. I deleted these files and re-ran the scraping. I assume that most of these were parts of the scraping where the internet went down or computer went to sleep.
- at the end it will provide a summary of the total number that had ocr done, and list out the ones where the OCR still didn't pass the quality check, and ask if thos files should be deleted (all pdf and txt associated with the file name). I found this helpful, since the issues was typically that the wrong pdf was downloaded (this could generally be solved by rerunning this pipeline, and changing the max workers to 1).
- all status updates are saved to `current_products_edited_txt_OCR.csv`



#####################################################################################################################################
added `nys_more_text_checking_after_OCR.py` which is a script that checks for the fuzzy match for agricultural use requirements and restricted-entry interval
it saves the output to `current_products_edited_txt_OCR_ag_rei_check.csv` with the column "agricultural_use_requirements_and_restricted_entry_interval" with values of both, ag, rei, or none.
The label is likely accurate if it passes the final_determination (not "Manual_Review") and has a value of either ag, rei, or both.


#####################################################################################################################################
Next step is to query the LLM and return responses as JSON format ready for the database
made the script `nys_gpt_query.py` which is similar to the EPA label query script, and added a parrallel version of this script for faster processing `nys_gpt_query_parallel.py`
- for now it filters to solely routine label types
- it also filters to only the routine labels with at least containing rei or ag use requirements to ensure including of pesticides relevant to plant agriculture
- it loops through the csv and saves the output json files to `output_json` directory following the `schema.json` format
      *TODO: consider adding a "product description" where the ai attempts to pull any general information from the label description, like this is an herbicide targeting leafy weeds or something like that
- it save the status of which pesticides have been queried and saves that status to a new csv `current_products_edited_txt_OCR_ag_rei_gpt_query.csv`




#####################################################################################################################################



-Next is to add more data to the output_json files in an altered json like the epa pipeline does, like mode of action, organic/conv, etc. add data from the below columns to the `altered_json` directory. use `nys_altered_json.py` for this

-no need to add this to the csv, since the data is somewhat difficult to add to a csv. get active ingredient names, codes, and percentages from the latest `old/Dec_ProductData_ActiveIngredients-2025-12-15-06-45-37.csv` each row is a different active ingredient-product ID combination, in the altered json, each pesticide (PESTICIDE ID) can have multiple active ingredients "PC NAME" and each active ingredient can only have one "PC Code" and one "ACTIVE INGREDIENT PERCENTAGE", and one nys active ingredient id "ACTIVE INGREDIENT ID". rename these in the json as "active_ingredient", "pc_code", "active_ingredient_percentage", and "nys_active_ingredient_id".

- also add other data from the current_products_edited_txt_OCR_ag_rei_gpt_query.csv file to the json after trade name including PRODUCT TYPE, LONG ISLAND USE RESTRICTION, Formulation, TOXICITY, PRODUCT USE, 

- also add the mode of action lookup, like in the web_application_old, where each active ingrediant has a mode of action code. use mode_of_action.xlsx as the source of mode of aciton codes


#####################################################################################################################################
The data from the llms takes raw information (poretty much) from the pesticide labels and structures it, however different labels can name the same disease or crop slightly differently, so a new script was made to standardize the names:
`nys_altered_json_target_classificaiton.py`

- it creates target_names_unified.csv and crop_names_unified.csv which unify the names, and there is also a editor page which can manually unify the names as well. Any manual editing should be done through the app
- in the script, it queries gpt to characterize the target names into main categories, like disease and insect, etc. and then tries to give all targets a general common name and sometimes scientific name if needed. To do this, first classify the target categories with this: 
`python3 nys_altered_json_target_classificaiton.py --classify --batch-size 200`
The batch size is kept small to try to not stress the llm too much, just giving it 200 targets at a time to classify, if its not sure, it assigns it as "Other"
`python3 nys_altered_json_target_classificaiton.py --refine --batch-size 600  `
This one has a larger batch size to try to keep all of the targets of one target typ and crop together in the prompt, so that the llm is more likely to unify targets like Venturia and scab as Apple Scab as target and Venturia spp. as species.

#####################################################################################################################################
Next is the `web_application_nys` that will take the json data from altered_json and use it in the web application. go to the web_application_nys to see the readme for the webapplication details. run it in venv:

cd /Users/sdc99/Documents/NYSPAD/web_application_nys
source .venv/bin/activate
python run_dev.py
