#!/usr/bin/env python3
"""
NYSPAD Data File Parser
Parses downloadable data files from NYSPAD to extract pesticide information and potential download links
"""

# Print immediately to show script is starting
import sys
print("🚀 NYSPAD Data Parser - Starting...", flush=True)
sys.stdout.flush()

import os
import csv
import json
import logging
print("  ✓ Imports: os, csv, json, logging", flush=True)

import requests
print("  ✓ Import: requests", flush=True)
sys.stdout.flush()

print("  ⏳ Importing pandas (this may take a moment)...", flush=True)
sys.stdout.flush()

# Try importing pandas - if it hangs, we'll skip it
PANDAS_AVAILABLE = False
pd = None

# Note: If pandas hangs here due to OneDrive sync issues, 
# the script will continue without it using basic CSV parsing
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
    print("  ✓ Import: pandas", flush=True)
except ImportError as e:
    print(f"  ⚠️  WARNING: Could not import pandas: {e}", flush=True)
    print("  The script will use basic CSV parsing instead.", flush=True)
    PANDAS_AVAILABLE = False
except Exception as e:
    print(f"  ⚠️  WARNING: Error importing pandas: {type(e).__name__}", flush=True)
    print("  This may be due to OneDrive sync issues with the virtual environment.", flush=True)
    print("  The script will use basic CSV parsing instead.", flush=True)
    print("  To fix: Move .venv outside OneDrive or reinstall pandas", flush=True)
    PANDAS_AVAILABLE = False

sys.stdout.flush()

print("  ⏳ Importing remaining modules...", flush=True)
sys.stdout.flush()

from typing import List, Dict, Optional, Union
import re
from urllib.parse import urljoin, urlparse
import time

print("  ✓ All imports successful", flush=True)
print()
sys.stdout.flush()

class NYSPADDataParser:
    def __init__(self, data_dir: str = "../../pipeline_critical_docs/nyspad_data"):
        """
        Initialize the NYSPAD data parser
        
        Args:
            data_dir: Directory to store downloaded data files
        """
        print(f"📁 Initializing parser...", flush=True)
        self.data_dir = data_dir
        self.nyspad_base_url = "https://extapps.dec.ny.gov/nyspad"
        
        print(f"  Creating session...", flush=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (ResearchBot; Pesticide Database Project; +https://github.com/your-repo)'
        })
        
        # Create data directory
        print(f"  Creating data directory: {data_dir}...", flush=True)
        try:
            os.makedirs(data_dir, exist_ok=True)
            print(f"  ✓ Directory ready", flush=True)
        except Exception as e:
            print(f"  ✗ Error creating directory: {e}", flush=True)
            raise
        
        # Setup logging
        print(f"  Setting up logging...", flush=True)
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('nyspad_data_parser.log'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
            print(f"  ✓ Logging configured", flush=True)
        except Exception as e:
            print(f"  ⚠️  Warning: Logging setup issue: {e}", flush=True)
            # Continue without file logging if there's an issue
            logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
            self.logger = logging.getLogger(__name__)
        
        print(f"✅ Parser initialized\n", flush=True)

    def download_nyspad_data_files(self) -> List[str]:
        """
        Download available data files from NYSPAD
        
        Returns:
            List of downloaded file paths
        """
        downloaded_files = []
        
        try:
            # Common NYSPAD data file URLs (these may need to be updated)
            data_urls = [
                "https://extapps.dec.ny.gov/nyspad/data/current_products.csv",
                "https://extapps.dec.ny.gov/nyspad/data/archival_products.csv",
                "https://extapps.dec.ny.gov/nyspad/data/product_data.csv",
                "https://extapps.dec.ny.gov/nyspad/data/pesticide_products.csv"
            ]
            
            print(f"  Checking {len(data_urls)} potential data file URLs...")
            
            for i, url in enumerate(data_urls, 1):
                try:
                    filename = os.path.basename(urlparse(url).path)
                    filepath = os.path.join(self.data_dir, filename)
                    
                    # Skip if file already exists
                    if os.path.exists(filepath):
                        print(f"  [{i}/{len(data_urls)}] ✓ {filename} (already exists)")
                        self.logger.info(f"File already exists: {filename}")
                        downloaded_files.append(filepath)
                        continue
                    
                    print(f"  [{i}/{len(data_urls)}] ⬇️  Downloading {filename}...", end=" ", flush=True)
                    self.logger.info(f"Downloading: {url}")
                    response = self.session.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        print(f"✓ Success ({len(response.content)} bytes)")
                        self.logger.info(f"Downloaded: {filename}")
                        downloaded_files.append(filepath)
                    else:
                        print(f"✗ Failed (HTTP {response.status_code})")
                        self.logger.warning(f"Failed to download {url}: {response.status_code}")
                        
                except Exception as e:
                    print(f"✗ Error: {str(e)[:50]}")
                    self.logger.error(f"Error downloading {url}: {e}")
                    continue
            
            if not downloaded_files:
                print("  ⚠️  No data files were successfully downloaded.")
                print("  ℹ️  This is normal if the URLs don't exist or have changed.")
            else:
                print(f"  ✅ Successfully processed {len(downloaded_files)} file(s)")
                    
        except Exception as e:
            self.logger.error(f"Error in download_nyspad_data_files: {e}")
            print(f"  ✗ Error: {e}")
        
        return downloaded_files

    def parse_csv_file(self, filepath: str) -> List[Dict]:
        """
        Parse a CSV data file from NYSPAD
        
        Args:
            filepath: Path to the CSV file
            
        Returns:
            List of parsed pesticide records
        """
        records = []
        
        try:
            self.logger.info(f"Parsing CSV file: {filepath}")
            
            if PANDAS_AVAILABLE and pd is not None:
                # Use pandas if available
                encodings = ['utf-8', 'latin-1', 'cp1252']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(filepath, encoding=encoding, low_memory=False)
                        self.logger.info(f"Successfully read file with {encoding} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    self.logger.error(f"Could not read file with any encoding: {filepath}")
                    return records
                
                # Convert to list of dictionaries
                for _, row in df.iterrows():
                    record = self._parse_csv_row(row, filepath)
                    if record:
                        records.append(record)
            else:
                # Fallback to basic CSV parsing
                self.logger.info("Using basic CSV parser (pandas not available)")
                encodings = ['utf-8', 'latin-1', 'cp1252']
                
                for encoding in encodings:
                    try:
                        with open(filepath, 'r', encoding=encoding) as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                record = self._parse_csv_row_dict(row, filepath)
                                if record:
                                    records.append(record)
                        self.logger.info(f"Successfully read file with {encoding} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        self.logger.warning(f"Error with {encoding} encoding: {e}")
                        continue
            
            self.logger.info(f"Parsed {len(records)} records from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error parsing CSV file {filepath}: {e}")
        
        return records

    def _parse_csv_row_dict(self, row: Dict, source_file: str) -> Optional[Dict]:
        """Parse a CSV row from a dictionary (fallback when pandas not available)"""
        try:
            record = {
                'source_file': os.path.basename(source_file),
                'epa_registration': self._extract_field(row, ['EPA_REG_NO', 'REG_NUM', 'EPA_REG', 'Registration_Number']),
                'product_name': self._extract_field(row, ['PRODUCT_NAME', 'Product_Name', 'NAME', 'Product']),
                'company_name': self._extract_field(row, ['COMPANY_NAME', 'Company_Name', 'REGISTRANT', 'Company']),
                'active_ingredients': self._extract_field(row, ['ACTIVE_INGREDIENTS', 'AI', 'Active_Ingredients']),
                'status': self._extract_field(row, ['STATUS', 'Status', 'REGISTRATION_STATUS']),
                'type': self._extract_field(row, ['TYPE', 'Type', 'PRODUCT_TYPE', 'Pesticide_Type']),
                'use': self._extract_field(row, ['USE', 'Use', 'USE_PATTERN', 'Use_Pattern']),
                'label_url': self._extract_field(row, ['LABEL_URL', 'Label_URL', 'PDF_URL', 'Document_URL']),
                'label_number': self._extract_field(row, ['LABEL_NO', 'Label_No', 'DOCUMENT_NO', 'Document_Number']),
                'accepted_date': self._extract_field(row, ['ACCEPTED_DATE', 'Accepted_Date', 'DATE_ACCEPTED']),
                'raw_data': row
            }
            
            if record['epa_registration'] or record['product_name']:
                return record
        except Exception as e:
            self.logger.warning(f"Error parsing CSV row: {e}")
        return None

    def _parse_csv_row(self, row, source_file: str) -> Optional[Dict]:
        """
        Parse a single CSV row into a standardized record
        
        Args:
            row: Pandas Series representing a CSV row
            source_file: Source file path for reference
            
        Returns:
            Parsed record dictionary or None if invalid
        """
        try:
            # Convert row to dictionary
            row_dict = row.to_dict()
            
            # Extract key fields (field names may vary)
            record = {
                'source_file': os.path.basename(source_file),
                'epa_registration': self._extract_field(row_dict, ['EPA_REG_NO', 'REG_NUM', 'EPA_REG', 'Registration_Number']),
                'product_name': self._extract_field(row_dict, ['PRODUCT_NAME', 'Product_Name', 'NAME', 'Product']),
                'company_name': self._extract_field(row_dict, ['COMPANY_NAME', 'Company_Name', 'REGISTRANT', 'Company']),
                'active_ingredients': self._extract_field(row_dict, ['ACTIVE_INGREDIENTS', 'AI', 'Active_Ingredients']),
                'status': self._extract_field(row_dict, ['STATUS', 'Status', 'REGISTRATION_STATUS']),
                'type': self._extract_field(row_dict, ['TYPE', 'Type', 'PRODUCT_TYPE', 'Pesticide_Type']),
                'use': self._extract_field(row_dict, ['USE', 'Use', 'USE_PATTERN', 'Use_Pattern']),
                'label_url': self._extract_field(row_dict, ['LABEL_URL', 'Label_URL', 'PDF_URL', 'Document_URL']),
                'label_number': self._extract_field(row_dict, ['LABEL_NO', 'Label_No', 'DOCUMENT_NO', 'Document_Number']),
                'accepted_date': self._extract_field(row_dict, ['ACCEPTED_DATE', 'Accepted_Date', 'DATE_ACCEPTED']),
                'raw_data': row_dict
            }
            
            # Only return records with essential information
            if record['epa_registration'] or record['product_name']:
                return record
            
        except Exception as e:
            self.logger.warning(f"Error parsing CSV row: {e}")
        
        return None

    def _extract_field(self, row_dict: Dict, possible_keys: List[str]) -> str:
        """
        Extract a field value using multiple possible key names
        
        Args:
            row_dict: Dictionary representing a CSV row
            possible_keys: List of possible key names
            
        Returns:
            Field value or empty string
        """
        for key in possible_keys:
            if key in row_dict:
                value = row_dict[key]
                # Handle pandas Series or regular dict
                if PANDAS_AVAILABLE and pd is not None:
                    if pd.notna(value):
                        value = str(value).strip()
                    else:
                        continue
                else:
                    if value is not None and value != '':
                        value = str(value).strip()
                    else:
                        continue
                
                if value and value.lower() not in ['nan', 'none', '']:
                    return value
        return ""

    def analyze_data_structure(self, filepath: str) -> Dict:
        """
        Analyze the structure of a data file to understand its format
        
        Args:
            filepath: Path to the data file
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            'filepath': filepath,
            'columns': [],
            'sample_records': [],
            'total_records': 0,
            'unique_epa_registrations': 0,
            'has_label_urls': False,
            'has_label_numbers': False
        }
        
        try:
            if PANDAS_AVAILABLE and pd is not None:
                # Use pandas if available
                df = pd.read_csv(filepath, encoding='utf-8', low_memory=False, nrows=1000)
                
                analysis['columns'] = list(df.columns)
                analysis['total_records'] = len(df)
                
                # Get sample records
                analysis['sample_records'] = df.head(3).to_dict('records')
                
                # Check for EPA registration numbers
                reg_columns = [col for col in df.columns if 'reg' in col.lower() or 'epa' in col.lower()]
                if reg_columns:
                    unique_regs = df[reg_columns[0]].nunique()
                    analysis['unique_epa_registrations'] = unique_regs
                
                # Check for label URLs
                url_columns = [col for col in df.columns if 'url' in col.lower() or 'link' in col.lower()]
                analysis['has_label_urls'] = len(url_columns) > 0
                
                # Check for label numbers
                label_columns = [col for col in df.columns if 'label' in col.lower() or 'document' in col.lower()]
                analysis['has_label_numbers'] = len(label_columns) > 0
            else:
                # Fallback to basic CSV analysis
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        analysis['columns'] = list(rows[0].keys())
                        analysis['total_records'] = len(rows)
                        analysis['sample_records'] = rows[:3]
                        
                        # Check for EPA registration numbers
                        reg_columns = [col for col in analysis['columns'] if 'reg' in col.lower() or 'epa' in col.lower()]
                        if reg_columns:
                            unique_regs = len(set(row.get(reg_columns[0], '') for row in rows if row.get(reg_columns[0])))
                            analysis['unique_epa_registrations'] = unique_regs
                        
                        # Check for label URLs
                        url_columns = [col for col in analysis['columns'] if 'url' in col.lower() or 'link' in col.lower()]
                        analysis['has_label_urls'] = len(url_columns) > 0
                        
                        # Check for label numbers
                        label_columns = [col for col in analysis['columns'] if 'label' in col.lower() or 'document' in col.lower()]
                        analysis['has_label_numbers'] = len(label_columns) > 0
            
        except Exception as e:
            self.logger.error(f"Error analyzing file structure {filepath}: {e}")
            analysis['error'] = str(e)
        
        return analysis

    def extract_download_links(self, records: List[Dict]) -> List[Dict]:
        """
        Extract potential download links from parsed records
        
        Args:
            records: List of parsed pesticide records
            
        Returns:
            List of download link information
        """
        download_links = []
        
        for record in records:
            try:
                # Check for direct label URLs
                if record.get('label_url'):
                    url = record['label_url']
                    if self._is_valid_pdf_url(url):
                        download_links.append({
                            'epa_registration': record['epa_registration'],
                            'product_name': record['product_name'],
                            'url': url,
                            'type': 'direct_url',
                            'label_number': record.get('label_number', ''),
                            'accepted_date': record.get('accepted_date', '')
                        })
                
                # Check for label numbers that might be used to construct URLs
                if record.get('label_number') and not record.get('label_url'):
                    # Try to construct potential URLs
                    constructed_urls = self._construct_potential_urls(record)
                    for url in constructed_urls:
                        download_links.append({
                            'epa_registration': record['epa_registration'],
                            'product_name': record['product_name'],
                            'url': url,
                            'type': 'constructed_url',
                            'label_number': record.get('label_number', ''),
                            'accepted_date': record.get('accepted_date', '')
                        })
                
            except Exception as e:
                self.logger.warning(f"Error extracting download links for record: {e}")
                continue
        
        return download_links

    def _is_valid_pdf_url(self, url: str) -> bool:
        """Check if URL appears to be a valid PDF link"""
        if not url or not isinstance(url, str):
            return False
        
        url_lower = url.lower()
        return ('pdf' in url_lower or 
                url_lower.endswith('.pdf') or
                'document' in url_lower or
                'label' in url_lower)

    def _construct_potential_urls(self, record: Dict) -> List[str]:
        """
        Construct potential download URLs based on available information
        
        Args:
            record: Parsed pesticide record
            
        Returns:
            List of potential URLs
        """
        urls = []
        
        try:
            label_number = record.get('label_number', '')
            epa_reg = record.get('epa_registration', '')
            
            if label_number:
                # Common URL patterns for NYSPAD documents
                base_patterns = [
                    f"https://extapps.dec.ny.gov/nyspad/documents/{label_number}.pdf",
                    f"https://extapps.dec.ny.gov/nyspad/labels/{label_number}.pdf",
                    f"https://extapps.dec.ny.gov/nyspad/files/{label_number}.pdf",
                    f"https://extapps.dec.ny.gov/nyspad/products/{label_number}/label.pdf"
                ]
                urls.extend(base_patterns)
            
            if epa_reg:
                # EPA-based patterns
                epa_patterns = [
                    f"https://extapps.dec.ny.gov/nyspad/products/{epa_reg}/label.pdf",
                    f"https://extapps.dec.ny.gov/nyspad/documents/{epa_reg}.pdf"
                ]
                urls.extend(epa_patterns)
                
        except Exception as e:
            self.logger.warning(f"Error constructing URLs: {e}")
        
        return urls

    def validate_download_links(self, download_links: List[Dict]) -> List[Dict]:
        """
        Validate download links by checking if they're accessible
        
        Args:
            download_links: List of download link information
            
        Returns:
            List of validated download links
        """
        validated_links = []
        
        for link_info in download_links:
            try:
                url = link_info['url']
                self.logger.info(f"Validating URL: {url}")
                
                # Make a HEAD request to check if URL is accessible
                response = self.session.head(url, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    # Check if it's actually a PDF
                    content_type = response.headers.get('content-type', '').lower()
                    if 'pdf' in content_type or url.lower().endswith('.pdf'):
                        link_info['validated'] = True
                        link_info['content_type'] = content_type
                        link_info['content_length'] = response.headers.get('content-length', '')
                        validated_links.append(link_info)
                        self.logger.info(f"Valid PDF link: {url}")
                    else:
                        self.logger.warning(f"URL not a PDF: {url} (content-type: {content_type})")
                else:
                    self.logger.warning(f"URL not accessible: {url} (status: {response.status_code})")
                
                # Be respectful with requests (increased delay for better server respect)
                time.sleep(1.0)
                
            except Exception as e:
                self.logger.warning(f"Error validating URL {link_info.get('url', 'unknown')}: {e}")
                continue
        
        return validated_links

    def download_pdf_from_link(self, link_info: Dict, download_dir: str = None) -> bool:
        """
        Download a PDF from a validated link
        
        Args:
            link_info: Download link information
            download_dir: Directory to save the PDF (defaults to self.data_dir)
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            if download_dir is None:
                download_dir = self.data_dir
            
            url = link_info['url']
            epa_reg = link_info.get('epa_registration', 'unknown')
            label_number = link_info.get('label_number', 'unknown')
            
            # Generate filename
            filename = f"{epa_reg}_{label_number}.pdf"
            filepath = os.path.join(download_dir, filename)
            
            # Skip if file already exists
            if os.path.exists(filepath):
                self.logger.info(f"File already exists: {filename}")
                return True
            
            # Download the PDF
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"Downloaded: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading PDF from {link_info.get('url', 'unknown')}: {e}")
            return False

    def process_all_data_files(self) -> Dict:
        """
        Process all available NYSPAD data files
        
        Returns:
            Summary of processing results
        """
        results = {
            'files_processed': 0,
            'total_records': 0,
            'download_links_found': 0,
            'validated_links': 0,
            'pdfs_downloaded': 0,
            'errors': [],
            'file_analyses': [],
            'download_links': []
        }
        
        try:
            # Download data files
            downloaded_files = self.download_nyspad_data_files()
            
            if not downloaded_files:
                print("\n⚠️  No files to process. Exiting.")
                return results
            
            print(f"\n📊 Step 2: Processing {len(downloaded_files)} file(s)...")
            print("-" * 60)
            
            for idx, filepath in enumerate(downloaded_files, 1):
                filename = os.path.basename(filepath)
                print(f"\n  [{idx}/{len(downloaded_files)}] Processing: {filename}")
                try:
                    # Analyze file structure
                    print(f"    📋 Analyzing file structure...", end=" ", flush=True)
                    analysis = self.analyze_data_structure(filepath)
                    results['file_analyses'].append(analysis)
                    print(f"✓ ({analysis.get('total_records', 0)} rows found)")
                    
                    # Parse records
                    print(f"    📝 Parsing records...", end=" ", flush=True)
                    records = self.parse_csv_file(filepath)
                    results['total_records'] += len(records)
                    results['files_processed'] += 1
                    print(f"✓ ({len(records)} records)")
                    
                    # Extract download links
                    print(f"    🔗 Extracting download links...", end=" ", flush=True)
                    download_links = self.extract_download_links(records)
                    results['download_links_found'] += len(download_links)
                    print(f"✓ ({len(download_links)} links found)")
                    
                    # Validate links
                    if download_links:
                        print(f"    ✅ Validating links...", end=" ", flush=True)
                        validated_links = self.validate_download_links(download_links)
                        results['validated_links'] += len(validated_links)
                        results['download_links'].extend(validated_links)
                        print(f"✓ ({len(validated_links)} valid)")
                    else:
                        validated_links = []
                        print(f"    ⚠️  No links to validate")
                    
                    # Download PDFs
                    if validated_links:
                        print(f"    ⬇️  Downloading PDFs...")
                        for link_idx, link_info in enumerate(validated_links, 1):
                            print(f"      [{link_idx}/{len(validated_links)}] {link_info.get('product_name', 'Unknown')[:40]}...", end=" ", flush=True)
                            if self.download_pdf_from_link(link_info):
                                results['pdfs_downloaded'] += 1
                                print("✓")
                            else:
                                print("✗")
                    else:
                        print(f"    ℹ️  No PDFs to download")
                    
                except Exception as e:
                    error_msg = f"Error processing file {filepath}: {e}"
                    print(f"    ✗ Error: {e}")
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
        except Exception as e:
            error_msg = f"Error in process_all_data_files: {e}"
            results['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return results

    def save_results(self, results: Dict, filename: str = "nyspad_data_analysis.json"):
        """Save analysis results to JSON file"""
        try:
            filepath = os.path.join(self.data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            self.logger.info(f"Results saved to: {filepath}")
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")


def main():
    """Main function to demonstrate usage"""
    print("=" * 60)
    print("NYSPAD Data Parser - Starting")
    print("=" * 60)
    
    parser = NYSPADDataParser()
    
    print("\n📥 Step 1: Downloading NYSPAD data files...")
    print("-" * 60)
    
    # Process all data files
    results = parser.process_all_data_files()
    
    print("\n" + "=" * 60)
    print("📊 Processing Complete - Summary")
    print("=" * 60)
    print(f"Files processed: {results['files_processed']}")
    print(f"Total records: {results['total_records']}")
    print(f"Download links found: {results['download_links_found']}")
    print(f"Validated links: {results['validated_links']}")
    print(f"PDFs downloaded: {results['pdfs_downloaded']}")
    
    if results['errors']:
        print(f"\n⚠️  Errors encountered: {len(results['errors'])}")
        for error in results['errors'][:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(results['errors']) > 5:
            print(f"  ... and {len(results['errors']) - 5} more errors")
    
    # Save results
    print("\n💾 Saving results...")
    parser.save_results(results)
    print("✅ Done!")


if __name__ == "__main__":
    print(f"Python: {sys.version.split()[0]}")
    print(f"Working directory: {os.getcwd()}")
    print()
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user (Ctrl+C)", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
