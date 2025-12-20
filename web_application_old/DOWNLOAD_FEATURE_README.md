# Pesticide Data Download Feature

## Overview
A new download feature has been added to the pesticide search web application that allows users to download detailed pesticide information in Excel (.xlsx) format. This includes:

1. **Individual Pesticide Download**: Download detailed information for a specific pesticide from the popup modal
2. **Filtered Results Download**: Download all filtered results from the guided filter section

## Features Added

### 1. Individual Pesticide Download API Endpoint
- **Route**: `/api/pesticide/<epa_reg_no>/download`
- **Method**: GET
- **Function**: `download_pesticide_excel(epa_reg_no)`
- **Location**: `web_application/pesticide_search.py`

### 2. Filtered Results Download API Endpoint
- **Route**: `/api/filter/download`
- **Method**: GET
- **Function**: `download_filtered_excel()`
- **Location**: `web_application/pesticide_search.py`
- **Parameters**: `crop` and `pest` query parameters

### 3. Frontend Download Buttons

#### Individual Pesticide Download
- **Location**: Modal popup in `web_application/templates/search.html`
- **Position**: Next to the "Latest EPA Label PDF" button
- **Style**: Green button with "Download This Page" text
- **URL**: `/api/pesticide/${pesticide.epa_reg_no}/download`

#### Filtered Results Download
- **Location**: Guided filter section in `web_application/templates/search.html`
- **Position**: Next to the "Apply Filter" button
- **Style**: Green button with "Download Results" text
- **Function**: `downloadFilteredResults()` JavaScript function
- **URL**: `/api/filter/download?crop=${crop}&pest=${pest}`

### 4. Excel File Structure

#### Individual Pesticide Download
The generated Excel file contains multiple sheets with comprehensive pesticide information:

#### Basic Information Sheet
- EPA Registration Number
- Trade Name
- Company
- Organic Status
- Signal Word
- PPE Requirements
- Alternative Names
- Label URL
- First Registration Date (if available)
- Physical Form (if available)

#### Active Ingredients Sheet
- Name
- Percentage
- Mode of Action

#### Application Information Sheet
- Crop
- Target Disease/Pest
- Low Rate
- High Rate
- Units
- REI (Re-entry Interval)
- PHI (Pre-harvest Interval)
- Application Method
- Max Applications per Season

#### Filtered Results Download
The generated Excel file contains a single sheet with all filtered pesticide results:

**Filtered Results Sheet**
- EPA Registration Number
- Trade Name
- Company
- Organic Status
- Active Ingredients
- Mode of Action
- Signal Word
- PPE
- Label URL
- Crop
- Target Disease/Pest
- Low Rate
- High Rate
- Units
- REI
- PHI
- Application Method
- Max Applications/Season

### 5. Excel Styling
- Professional blue header styling
- Proper column widths
- Centered alignment for headers
- Clean, readable format
- Optimized column widths for filtered results table

## Technical Implementation

### Dependencies Added
- `openpyxl==3.1.2` - Added to `pipeline_critical_docs/requirements.txt`
- `send_file` - Added to Flask imports

### Code Changes

#### Backend (`pesticide_search.py`)
1. **Imports Added**:
   ```python
   from flask import send_file
   from openpyxl import Workbook
   from openpyxl.styles import Font, Alignment, PatternFill
   import tempfile
   import io
   ```

2. **New Routes**:
   ```python
   @app.route('/api/pesticide/<epa_reg_no>/download')
   def download_pesticide_excel(epa_reg_no):
   
   @app.route('/api/filter/download')
   def download_filtered_excel():
   ```

#### Frontend (`search.html`)
1. **Individual Pesticide Download Button Added**:
   ```html
   <a href="/api/pesticide/${pesticide.epa_reg_no}/download" 
      class="search-button" 
      style="text-decoration:none; background: #28a745;">
      Download This Page
   </a>
   ```

2. **Filtered Results Download Button Added**:
   ```html
   <button id="downloadFilteredBtn" class="search-button" 
           style="background: #28a745; margin-left: 10px;" 
           onclick="downloadFilteredResults()">
       Download Results
   </button>
   ```

3. **JavaScript Function Added**:
   ```javascript
   function downloadFilteredResults() {
       // Get current filter values and trigger download
   }
   ```

## Usage

### Individual Pesticide Download
1. Search for a pesticide in the web application
2. Click on a pesticide result to open the detailed modal
3. Click the green "Download This Page" button next to the EPA Label PDF link
4. The browser will automatically download the Excel file
5. The filename will be in the format: `{Trade_Name}_{EPA_Reg_No}.xlsx`

### Filtered Results Download
1. Navigate to the guided filter section
2. Select a crop and/or pest from the dropdown menus
3. Click "Apply Filter" to see the filtered results
4. Click the green "Download Results" button next to the Apply Filter button
5. The browser will automatically download the Excel file with all filtered results
6. The filename will be in the format: `filtered_pesticides_crop_{crop}_pest_{pest}.xlsx`

## File Naming

### Individual Pesticide Download
- Files are automatically named using the pesticide's trade name and EPA registration number
- Invalid characters are removed from filenames
- Format: `{Trade_Name}_{EPA_Reg_No}.xlsx`

### Filtered Results Download
- Files are automatically named using the filter parameters
- Invalid characters are removed from filenames
- Format: `filtered_pesticides_crop_{crop}_pest_{pest}.xlsx`
- If no filters are applied, format: `filtered_pesticides_all.xlsx`

## Error Handling

### Individual Pesticide Download
- Returns 404 if pesticide not found
- Returns 400 if data format is invalid
- Returns 500 with error message if Excel generation fails
- Graceful handling of missing data fields (shows "N/A")

### Filtered Results Download
- Returns 404 if no results found for the specified filters
- Returns 500 with error message if Excel generation fails
- Graceful handling of missing data fields (shows "N/A")
- Validates filter parameters before processing

## Testing
The features have been tested with:
- ✅ Individual pesticide Excel generation with sample data
- ✅ Filtered results Excel generation with sample data
- ✅ Flask app imports successfully with both endpoints
- ✅ All required dependencies available
- ✅ Proper file download headers
- ✅ Filter parameter validation

## Browser Compatibility
- Works with all modern browsers that support file downloads
- Uses standard HTTP file download mechanism
- No JavaScript dependencies for download functionality
