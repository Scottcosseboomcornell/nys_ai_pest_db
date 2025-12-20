# NYSPAD Pesticide Label Automation

This document provides comprehensive solutions for automating the download of pesticide label PDFs from the New York State Pesticide Administration Database (NYSPAD).

## Problem Statement

The NYSPAD website (https://extapps.dec.ny.gov/nyspad/products) presents several challenges for automation:

1. **No Public API**: NYSPAD doesn't provide a public API for accessing pesticide data
2. **Dynamic URLs**: The search interface uses JavaScript and doesn't change URLs when searching
3. **Complex Link Structure**: Download links use dynamic identifiers without clear patterns
4. **Modal-based Interface**: Product details are shown in modals, making direct URL access difficult

## Solutions Provided

### 1. Selenium Web Scraper (`NY_scraping/nyspad_scraper.py`)

**Best for**: Comprehensive scraping of the NYSPAD website

**Features**:
- Handles dynamic JavaScript content
- Searches by product name or registration number
- Extracts detailed product information
- Downloads PDF documents
- Respectful rate limiting
- Comprehensive error handling

**Usage**:
```python
from nyspad_scraper import NYSPADScraper

# Basic usage
with NYSPADScraper(headless=True, delay=2.0) as scraper:
    # Search for specific pesticide
    results = scraper.search_pesticide("Admire Pro")
    
    if results:
        # Get details and download
        details = scraper.get_pesticide_details(results[0]['element'])
        for doc in details.get('documents', []):
            scraper.download_pdf(doc)

# Bulk scraping
with NYSPADScraper() as scraper:
    all_results = scraper.scrape_all_pesticides()
    scraper.save_results(all_results)
```

**Requirements**:
- Chrome browser installed
- ChromeDriver (automatically managed by webdriver-manager)

### 2. NYSPAD Data File Parser (`NY_scraping/nyspad_data_parser.py`)

**Best for**: Processing downloadable data files from NYSPAD

**Features**:
- Downloads and parses NYSPAD data files
- Extracts potential download links
- Validates link accessibility
- Constructs potential URLs from label numbers
- Handles various file formats and encodings

**Usage**:
```python
from nyspad_data_parser import NYSPADDataParser

parser = NYSPADDataParser()

# Process all available data files
results = parser.process_all_data_files()

# Analyze specific file structure
analysis = parser.analyze_data_structure("path/to/data.csv")

# Extract and validate download links
records = parser.parse_csv_file("path/to/data.csv")
download_links = parser.extract_download_links(records)
validated_links = parser.validate_download_links(download_links)
```

### 3. Integrated Pipeline (`NY_scraping/nyspad_integration.py`)

**Best for**: Seamless integration with existing pesticide processing pipeline

**Features**:
- Combines NYSPAD approaches for maximum coverage
- Identifies missing pesticides not in current pipeline
- Downloads and processes new labels
- Integrates with existing AI processing
- Updates web application

**Usage**:
```python
from nyspad_integration import NYSPADIntegration

integration = NYSPADIntegration()

# Find NY-specific pesticides
ny_pesticides = integration.find_nyspad_specific_pesticides()

# Download missing labels
download_results = integration.download_missing_labels()

# Full integration with pipeline
results = integration.integrate_with_pipeline(
    process_new_labels=True,
    update_web_app=False
)
```

## Installation

1. **Install additional dependencies**:
```bash
pip install -r main_pipeline_scripts/NY_scraping/nyspad_requirements.txt
```

2. **Install Chrome browser** (for Selenium):
   - macOS: `brew install --cask google-chrome`
   - Ubuntu: `sudo apt-get install google-chrome-stable`
   - Windows: Download from https://www.google.com/chrome/

3. **ChromeDriver** will be automatically managed by webdriver-manager

## Quick Start

```bash
# Install additional dependencies
pip install -r main_pipeline_scripts/NY_scraping/nyspad_requirements.txt

# Try the NYSPAD data parser first
cd main_pipeline_scripts/NY_scraping
python nyspad_data_parser.py

# Or use the integrated approach
python nyspad_integration.py
```

## Recommended Approach

### For Maximum Coverage:

1. **Start with NYSPAD Data Parser** - Process downloadable data files
2. **Use Selenium Scraper** - For comprehensive web scraping
3. **Use Integration Script** - For automated pipeline updates

### Example Workflow:

```python
# 1. Use NYSPAD data parser for bulk data processing
parser = NYSPADDataParser()
data_results = parser.process_all_data_files()

# 2. Use Selenium scraper for specific searches
with NYSPADScraper() as scraper:
    results = scraper.search_pesticide("Admire Pro")
    # Process results...

# 3. Use integration for pipeline updates
integration = NYSPADIntegration()
integration_results = integration.integrate_with_pipeline()
```

## Legal and Ethical Considerations

1. **Respect robots.txt**: Check NYSPAD's robots.txt file
2. **Rate Limiting**: Use delays between requests (2-3 seconds recommended)
3. **Terms of Service**: Review NYSPAD's terms of use
4. **Data Usage**: Ensure compliance with data usage policies
5. **Server Load**: Be mindful of server resources

## Troubleshooting

### Common Issues:

1. **ChromeDriver Issues**:
   - Ensure Chrome browser is installed
   - webdriver-manager should handle driver updates automatically

2. **Rate Limiting**:
   - Increase delay between requests
   - Use headless mode to reduce resource usage

3. **Dynamic Content**:
   - Increase wait times for page loads
   - Use explicit waits instead of sleep

4. **File Permissions**:
   - Ensure write permissions for download directories
   - Check disk space availability

### Debug Mode:

```python
# Run scraper in non-headless mode for debugging
with NYSPADScraper(headless=False, delay=5.0) as scraper:
    # Your scraping code here
    pass
```

## Performance Optimization

1. **Parallel Processing**: Use multiple browser instances for large-scale scraping
2. **Caching**: Cache search results to avoid repeated API calls
3. **Incremental Updates**: Only process new or updated pesticides
4. **Error Recovery**: Implement retry logic for failed downloads

## Monitoring and Logging

All scripts include comprehensive logging:
- File logging: `nyspad_scraper.log`, `epa_ppls_enhanced.log`, etc.
- Console output for real-time monitoring
- JSON result files for analysis

## Future Enhancements

1. **Database Integration**: Store results in a database for better querying
2. **Scheduled Updates**: Implement cron jobs for regular updates
3. **Web Interface**: Create a web interface for monitoring and control
4. **API Development**: Build a REST API for accessing the collected data

## Support

For issues or questions:
1. Check the log files for detailed error messages
2. Review the troubleshooting section
3. Ensure all dependencies are properly installed
4. Verify network connectivity and permissions
