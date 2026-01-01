#!/usr/bin/env python3
"""
NYSPAD Registered Products Downloader
Downloads the registered-products.zip file from the NYSPAD website
"""

import os
import logging
import requests
import zipfile
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup


class NYSPADDownloader:
    def __init__(self, download_dir: Optional[str] = None, base_url: str = "https://extapps.dec.ny.gov/nyspad/"):
        """
        Initialize the NYSPAD downloader
        
        Args:
            download_dir: Directory to save downloaded files (default: nyspad_csv_downloads next to this script)
            base_url: Base URL of the NYSPAD website
        """
        # Default to a dedicated downloads directory next to this script if not specified
        if download_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            download_dir = os.path.join(script_dir, "nyspad_csv_downloads")
        
        self.download_dir = download_dir
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create download directory
        os.makedirs(download_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('nyspad_downloader.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def find_download_link(self, filename: str) -> Optional[str]:
        """
        Scrape the NYSPAD page to find the download link for a specific file
        
        Args:
            filename: Name of the file to find (e.g., "registered-products.zip")
        
        Returns:
            URL of the download link if found, None otherwise
        """
        try:
            self.logger.info(f"Fetching page: {self.base_url}")
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for links containing the filename
            filename_lower = filename.lower()
            filename_base = filename_lower.replace('.zip', '').replace('-', ' ')
            
            # Look for links containing the filename or related terms
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '').lower()
                link_text = link.get_text().lower()
                
                # Check if href or link text contains the filename
                if filename_lower in href or filename_base in href or filename_base in link_text:
                    full_url = urljoin(self.base_url, link.get('href'))
                    self.logger.info(f"Found potential download link: {full_url}")
                    return full_url
            
            # Also check for direct download URLs in the page content
            page_text = response.text
            if filename in page_text:
                # Try to extract the URL from the page
                import re
                pattern = rf'https?://[^\s"\'<>]+{re.escape(filename)}'
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    self.logger.info(f"Found download URL in page content: {matches[0]}")
                    return matches[0]
            
            self.logger.warning(f"Could not find download link for {filename} on the page")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding download link: {str(e)}")
            return None
    
    def download_file(self, url: str, filename: str = "registered-products.zip") -> bool:
        """
        Download a file from the given URL
        
        Args:
            url: URL of the file to download
            filename: Name to save the file as
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            filepath = os.path.join(self.download_dir, filename)
            
            self.logger.info(f"Downloading from: {url}")
            self.logger.info(f"Saving to: {filepath}")
            
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))
            if total_size:
                self.logger.info(f"File size: {total_size / (1024*1024):.2f} MB")
            
            # Download with progress
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            percent = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Log every MB
                                self.logger.info(f"Downloaded: {downloaded / (1024*1024):.2f} MB ({percent:.1f}%)")
            
            self.logger.info(f"Successfully downloaded: {filepath}")
            self.logger.info(f"Total size: {downloaded / (1024*1024):.2f} MB")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading file: {str(e)}")
            return False
    
    def unzip_file(self, zip_path: str, extract_to: Optional[str] = None) -> bool:
        """
        Unzip a file to the specified directory
        
        Args:
            zip_path: Path to the zip file
            extract_to: Directory to extract to (default: same directory as zip file)
            
        Returns:
            True if extraction successful, False otherwise
        """
        try:
            if extract_to is None:
                extract_to = os.path.dirname(zip_path)
            
            self.logger.info(f"Extracting {zip_path} to {extract_to}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of files in the zip
                file_list = zip_ref.namelist()
                self.logger.info(f"Found {len(file_list)} file(s) in archive")
                
                # Extract all files
                zip_ref.extractall(extract_to)
                
                self.logger.info(f"Successfully extracted {len(file_list)} file(s) to {extract_to}")
                
                # Log extracted file names
                for filename in file_list[:10]:  # Log first 10 files
                    self.logger.info(f"  - {filename}")
                if len(file_list) > 10:
                    self.logger.info(f"  ... and {len(file_list) - 10} more file(s)")
            
            return True
            
        except zipfile.BadZipFile:
            self.logger.error(f"Error: {zip_path} is not a valid zip file")
            return False
        except Exception as e:
            self.logger.error(f"Error extracting zip file: {str(e)}")
            return False
    
    def download_and_unzip_file(self, filename: str, direct_url: Optional[str] = None) -> bool:
        """
        Download and unzip a file from NYSPAD
        
        Args:
            filename: Name of the file to download (e.g., "registered-products.zip")
            direct_url: Optional direct URL to the file. If not provided, will try to find it.
            
        Returns:
            True if download and extraction successful, False otherwise
        """
        if direct_url:
            self.logger.info(f"Using provided direct URL for {filename}")
            success = self.download_file(direct_url, filename)
        else:
            # Try to find the download link
            download_url = self.find_download_link(filename)
            
            if not download_url:
                # Try some common URL patterns
                self.logger.info(f"Trying common URL patterns for {filename}...")
                common_patterns = [
                    f"{self.base_url}data/{filename}",
                    f"{self.base_url}downloads/{filename}",
                    f"{self.base_url}files/{filename}",
                    f"{self.base_url}{filename}",
                ]
                
                for pattern_url in common_patterns:
                    self.logger.info(f"Trying: {pattern_url}")
                    try:
                        response = self.session.head(pattern_url, timeout=10)
                        if response.status_code == 200:
                            download_url = pattern_url
                            self.logger.info(f"Found valid URL: {download_url}")
                            break
                    except:
                        continue
            
            if download_url:
                success = self.download_file(download_url, filename)
            else:
                self.logger.error(f"Could not find or access the download URL for {filename}")
                return False
        
        if success:
            # Unzip the file after successful download
            zip_path = os.path.join(self.download_dir, filename)
            if os.path.exists(zip_path):
                self.logger.info(f"Starting extraction of {filename}...")
                unzip_success = self.unzip_file(zip_path)
                if unzip_success:
                    self.logger.info(f"Download and extraction of {filename} completed successfully!")
                else:
                    self.logger.warning(f"Download of {filename} succeeded but extraction failed")
            else:
                self.logger.warning(f"Downloaded file {filename} not found at expected path")
        
        return success


def main():
    """Main function to run the downloader"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download registered-products.zip and product-open-data.zip from NYSPAD')
    parser.add_argument('--output-dir', '-o', default=None, 
                       help='Directory to save the downloaded files (default: NY_scraping folder)')
    parser.add_argument('--url-registered', default=None,
                       help='Direct URL to the registered-products.zip file (optional)')
    parser.add_argument('--url-product-data', default=None,
                       help='Direct URL to the product-open-data.zip file (optional)')
    parser.add_argument('--skip-registered', action='store_true',
                       help='Skip downloading registered-products.zip')
    parser.add_argument('--skip-product-data', action='store_true',
                       help='Skip downloading product-open-data.zip')
    
    args = parser.parse_args()
    
    downloader = NYSPADDownloader(download_dir=args.output_dir)
    
    # Download both files
    success_registered = True
    success_product_data = True
    
    if not args.skip_registered:
        downloader.logger.info("=" * 60)
        downloader.logger.info("Downloading registered-products.zip")
        downloader.logger.info("=" * 60)
        success_registered = downloader.download_and_unzip_file("registered-products.zip", direct_url=args.url_registered)
    else:
        downloader.logger.info("Skipping registered-products.zip download")
    
    if not args.skip_product_data:
        downloader.logger.info("=" * 60)
        downloader.logger.info("Downloading product-open-data.zip")
        downloader.logger.info("=" * 60)
        success_product_data = downloader.download_and_unzip_file("product-open-data.zip", direct_url=args.url_product_data)
    else:
        downloader.logger.info("Skipping product-open-data.zip download")
    
    success = success_registered and success_product_data
    
    if success:
        print("Download and extraction completed successfully!")
        
        # Analyze the extracted CSV file
        try:
            import pandas as pd
            import re
            
            csv_path = os.path.join(downloader.download_dir, "current_products.csv")
            
            if not os.path.exists(csv_path):
                print(f"Warning: {csv_path} not found. Checking for other CSV files...")
                # Try to find any CSV file in the download directory
                csv_files = [f for f in os.listdir(downloader.download_dir) if f.endswith('.csv')]
                if csv_files:
                    csv_path = os.path.join(downloader.download_dir, csv_files[0])
                    print(f"Using: {csv_path}")
                else:
                    print("No CSV files found in the extracted archive.")
                    return 0
            
            current_products_df = pd.read_csv(csv_path)
            
            # Print the first 10 rows
            print("\nFirst 10 rows of the dataframe:")
            print(current_products_df.head(10))
            
            # Print the number of rows in the dataframe
            print(f"\nNumber of rows in dataframe: {len(current_products_df)}")
            
            # Add PRODUCT TYPE column by looking up from Dec_ProductData_ProductType CSV
            print("\n" + "=" * 60)
            print("Adding PRODUCT TYPE column...")
            print("=" * 60)
            
            # Find the newest Dec_ProductData_ProductType CSV file
            import glob
            product_type_pattern = os.path.join(downloader.download_dir, "Dec_ProductData_ProductType-*.csv")
            product_type_files = glob.glob(product_type_pattern)
            
            if not product_type_files:
                print(f"Warning: No Dec_ProductData_ProductType CSV file found in {downloader.download_dir}")
            else:
                # Get the newest file by sorting by modification time
                newest_product_type_file = max(product_type_files, key=os.path.getmtime)
                print(f"Using ProductType lookup file: {os.path.basename(newest_product_type_file)}")
                
                try:
                    # Read the ProductType CSV
                    product_type_df = pd.read_csv(newest_product_type_file)
                    print(f"Loaded {len(product_type_df)} rows from ProductType file")
                    
                    # Create a lookup dictionary: PRODUCT NAME -> PRODUCT TYPE(s)
                    # Handle multiple types per product name by collecting all unique types
                    lookup_dict = {}
                    for _, row in product_type_df.iterrows():
                        product_name = str(row["PRODUCT NAME"]).strip()
                        product_type = str(row["PRODUCT TYPE"]).strip()
                        
                        if product_name not in lookup_dict:
                            lookup_dict[product_name] = set()
                        lookup_dict[product_name].add(product_type)
                    
                    # Convert sets to sorted comma-separated strings
                    for product_name in lookup_dict:
                        lookup_dict[product_name] = ", ".join(sorted(lookup_dict[product_name]))
                    
                    print(f"Created lookup dictionary with {len(lookup_dict)} unique product names")
                    
                    # Perform the lookup
                    if "ProductName" in current_products_df.columns:
                        # Map ProductName to PRODUCT TYPE using exact match
                        current_products_df["PRODUCT TYPE"] = current_products_df["ProductName"].apply(
                            lambda x: lookup_dict.get(str(x).strip(), "") if pd.notna(x) else ""
                        )
                        
                        # Count matches
                        matches = (current_products_df["PRODUCT TYPE"] != "").sum()
                        print(f"Matched {matches} out of {len(current_products_df)} products ({matches/len(current_products_df)*100:.1f}%)")
                        print(f"Added 'PRODUCT TYPE' column with {matches} matches")
                    else:
                        print(f"Warning: 'ProductName' column not found in current_products.csv")
                        print(f"Available columns: {list(current_products_df.columns)}")
                        
                except Exception as e:
                    print(f"Error adding PRODUCT TYPE column: {str(e)}")
                    import traceback
                    traceback.print_exc()

            def _norm_col_name(name: str) -> str:
                return re.sub(r"[^a-z0-9]+", "", str(name).lower())

            def _find_col(df: "pd.DataFrame", *candidates: str) -> Optional[str]:
                col_map = {_norm_col_name(c): c for c in df.columns}
                for cand in candidates:
                    key = _norm_col_name(cand)
                    if key in col_map:
                        return col_map[key]
                return None

            def _clean_key_series(s: "pd.Series") -> "pd.Series":
                # Normalize identifiers that might be read as numbers (e.g., "100-1234" or "12345.0")
                return (
                    s.astype(str)
                    .str.strip()
                    .str.replace(r"\.0$", "", regex=True)
                )

            def _norm_alnum_series(s: "pd.Series") -> "pd.Series":
                """
                Aggressive normalizer for cross-file joins:
                - lowercase
                - remove ALL non-alphanumeric characters (spaces, punctuation, slashes, etc.)
                This is necessary because NYSPAD/DEC identifiers and names frequently differ by punctuation.
                """
                return (
                    s.astype(str)
                    .str.strip()
                    .str.lower()
                    .str.replace(r"[^a-z0-9]+", "", regex=True)
                )

            # Add Formulation and Long Island restriction from newest Dec_ProductData-*.csv
            print("\n" + "=" * 60)
            print("Adding Formulation / Long Island restriction columns...")
            print("=" * 60)

            dec_product_pattern = os.path.join(downloader.download_dir, "Dec_ProductData-*.csv")
            dec_product_files = glob.glob(dec_product_pattern)

            if not dec_product_files:
                print(f"Warning: No Dec_ProductData CSV file found in {downloader.download_dir}")
            else:
                newest_dec_product_file = max(dec_product_files, key=os.path.getmtime)
                print(f"Using Dec_ProductData lookup file: {os.path.basename(newest_dec_product_file)}")

                try:
                    dec_df = pd.read_csv(newest_dec_product_file)
                    print(f"Loaded {len(dec_df)} rows from Dec_ProductData file")

                    epa_col = _find_col(dec_df, "EPA REGISTRATION NUMBER", "EPA_REGISTRATION_NUMBER", "EPA REGISTRATION NO")
                    formulation_col = _find_col(dec_df, "Formulation", "FORMULATION")
                    li_col = _find_col(dec_df, "LONG ISLAND USE RESTRICTION", "LONG_ISLAND_USE_RESTRICTION")

                    if "Product No." not in current_products_df.columns:
                        print("Warning: 'Product No.' column not found in current_products.csv; cannot join Dec_ProductData fields.")
                    elif not all([epa_col, formulation_col, li_col]):
                        print("Warning: Missing required columns in Dec_ProductData CSV; cannot add formulation/LI restriction.")
                        print(f"Detected columns: epa={epa_col}, formulation={formulation_col}, li_restriction={li_col}")
                    else:
                        dec_subset = dec_df[[epa_col, formulation_col, li_col]].copy()
                        dec_subset["_epa_key"] = _norm_alnum_series(_clean_key_series(dec_subset[epa_col]))
                        dec_subset = dec_subset.drop_duplicates(subset=["_epa_key"], keep="last")

                        current_products_df["_epa_key"] = _norm_alnum_series(_clean_key_series(current_products_df["Product No."]))

                        current_products_df = current_products_df.merge(
                            dec_subset,
                            how="left",
                            left_on="_epa_key",
                            right_on="_epa_key",
                        )

                        # Keep a single "Formulation" column with human-readable values (S=Solid, L=Liquid)
                        raw_formulation = current_products_df[formulation_col].astype(str).str.strip()
                        current_products_df["Formulation"] = (
                            raw_formulation.str.upper().map({"S": "Solid", "L": "Liquid"}).fillna("")
                        )

                        # If the source column wasn't literally named "Formulation", drop it to avoid redundancy
                        if formulation_col != "Formulation" and formulation_col in current_products_df.columns:
                            current_products_df = current_products_df.drop(columns=[formulation_col])

                        # Normalize Long Island restriction to TRUE/FALSE
                        def _map_li(val) -> str:
                            if pd.isna(val):
                                return ""
                            v = str(val).strip().upper()
                            if v in {"Y", "YES", "TRUE"}:
                                return "TRUE"
                            if v in {"N", "NO", "FALSE"}:
                                return "FALSE"
                            return ""

                        current_products_df["LONG ISLAND USE RESTRICTION"] = current_products_df[li_col].apply(_map_li)
                        # Drop original LI column if it was differently named
                        if li_col != "LONG ISLAND USE RESTRICTION" and li_col in current_products_df.columns:
                            current_products_df = current_products_df.drop(columns=[li_col])

                        # Drop the join helper column from right-hand side
                        drop_cols = [c for c in ["_epa_key", epa_col] if c in current_products_df.columns]
                        if drop_cols:
                            current_products_df = current_products_df.drop(columns=drop_cols)
                        print("Added Dec_ProductData fields (Formulation, Long Island restriction).")

                except Exception as e:
                    print(f"Error adding Dec_ProductData fields: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # Filter by "Registration Status" == "REGISTERED"
            if "Registration Status" in current_products_df.columns:
                registered_df = current_products_df[current_products_df["Registration Status"].isin(["REGISTERED"])]
                
                # Print the first 10 rows of the filtered dataframe
                print("\nFirst 10 rows of REGISTERED products:")
                print(registered_df.head(10))
                
                # Print the number of rows in the filtered dataframe
                print(f"\nNumber of REGISTERED rows: {len(registered_df)}")

                # Lookup PRODUCT ID from newest Dec_ProductData-*.csv using concatenated keys:
                # (Product No. + ProductName) in current products vs (EPA REGISTRATION NUMBER + PRODUCT NAME) in Dec_ProductData,
                # with BOTH sides filtered to Registration Status in {REGISTERED}.
                print("\n" + "=" * 60)
                print("Looking up PRODUCT ID (REGISTERED, ProductNo+ProductName match)...")
                print("=" * 60)

                registered_df["PRODUCT ID"] = ""
                statuses_for_product_id = {"REGISTERED"}

                try:
                    dec_product_pattern = os.path.join(downloader.download_dir, "Dec_ProductData-*.csv")
                    dec_product_files = glob.glob(dec_product_pattern)

                    if not dec_product_files:
                        print(f"Warning: No Dec_ProductData CSV file found in {downloader.download_dir}; cannot lookup PRODUCT ID.")
                    else:
                        newest_dec_product_file = max(dec_product_files, key=os.path.getmtime)
                        print(f"Using Dec_ProductData lookup file: {os.path.basename(newest_dec_product_file)}")

                        dec_df = pd.read_csv(newest_dec_product_file)
                        print(f"Loaded {len(dec_df)} rows from Dec_ProductData file")

                        dec_status_col = _find_col(dec_df, "Registration Status", "REGISTRATION STATUS", "REGISTRATION_STATUS")
                        dec_epa_col = _find_col(dec_df, "EPA REGISTRATION NUMBER", "EPA_REGISTRATION_NUMBER", "EPA REGISTRATION NO")
                        dec_name_col = _find_col(dec_df, "PRODUCT NAME", "Product Name", "PRODUCTNAME")
                        dec_pid_col = _find_col(dec_df, "PRODUCT ID", "PRODUCT_ID", "PRODUCTID")

                        if not all([dec_status_col, dec_epa_col, dec_name_col, dec_pid_col]):
                            print("Warning: Missing required columns in Dec_ProductData; cannot lookup PRODUCT ID.")
                            print(
                                f"Detected columns: status={dec_status_col}, epa={dec_epa_col}, name={dec_name_col}, product_id={dec_pid_col}"
                            )
                        elif "Product No." not in registered_df.columns or "ProductName" not in registered_df.columns:
                            print("Warning: 'Product No.' or 'ProductName' not found in current products; cannot lookup PRODUCT ID.")
                        else:
                            # Filter both sides to REGISTERED/DISCONTINUED for PRODUCT ID lookup
                            dec_subset = dec_df[
                                dec_df[dec_status_col].astype(str).str.strip().str.upper().isin(statuses_for_product_id)
                            ].copy()

                            dec_subset[dec_epa_col] = _norm_alnum_series(_clean_key_series(dec_subset[dec_epa_col]))
                            dec_subset[dec_name_col] = _norm_alnum_series(dec_subset[dec_name_col])
                            dec_subset[dec_pid_col] = _clean_key_series(dec_subset[dec_pid_col])

                            dec_subset["_concat_key"] = dec_subset[dec_epa_col] + "||" + dec_subset[dec_name_col]
                            dec_subset = dec_subset.dropna(subset=["_concat_key"])

                            # Build mapping; if duplicates exist, keep last occurrence
                            pid_map = (
                                dec_subset.drop_duplicates(subset=["_concat_key"], keep="last")
                                .set_index("_concat_key")[dec_pid_col]
                                .to_dict()
                            )

                            # Apply mapping back onto registered_df (REGISTERED + DISCONTINUED rows)
                            registered_df["_concat_key"] = (
                                _norm_alnum_series(_clean_key_series(registered_df["Product No."]))
                                + "||"
                                + _norm_alnum_series(registered_df["ProductName"])
                            )

                            status_mask = (
                                registered_df["Registration Status"].astype(str).str.strip().str.upper().isin(statuses_for_product_id)
                            )
                            registered_df.loc[status_mask, "PRODUCT ID"] = registered_df.loc[status_mask, "_concat_key"].map(pid_map).fillna("")

                            registered_df = registered_df.drop(columns=["_concat_key"])

                            pid_matches = (registered_df["PRODUCT ID"] != "").sum()
                            print(f"PRODUCT ID populated for {pid_matches} rows (REGISTERED + DISCONTINUED).")

                except Exception as e:
                    print(f"Error looking up PRODUCT ID: {str(e)}")
                    import traceback
                    traceback.print_exc()

                # Add TOXICITY as comma-separated list per PRODUCT ID from newest Dec_ProductData_Toxicity-*.csv
                print("\n" + "=" * 60)
                print("Adding TOXICITY column...")
                print("=" * 60)

                toxicity_pattern = os.path.join(downloader.download_dir, "Dec_ProductData_Toxicity-*.csv")
                toxicity_files = glob.glob(toxicity_pattern)

                if not toxicity_files:
                    print(f"Warning: No Dec_ProductData_Toxicity CSV file found in {downloader.download_dir}")
                    registered_df["TOXICITY"] = ""
                else:
                    newest_toxicity_file = max(toxicity_files, key=os.path.getmtime)
                    print(f"Using Toxicity lookup file: {os.path.basename(newest_toxicity_file)}")

                    try:
                        tox_df = pd.read_csv(newest_toxicity_file)
                        print(f"Loaded {len(tox_df)} rows from Toxicity file")

                        tox_pid_col = _find_col(tox_df, "PRODUCT ID", "PRODUCT_ID", "PRODUCTID")
                        tox_col = _find_col(tox_df, "TOXICITY")

                        if not tox_pid_col or not tox_col:
                            print("Warning: Missing required columns in Toxicity CSV; cannot add TOXICITY.")
                            print(f"Detected columns: product_id={tox_pid_col}, toxicity={tox_col}")
                            registered_df["TOXICITY"] = ""
                        else:
                            tox_df[tox_pid_col] = _clean_key_series(tox_df[tox_pid_col])
                            tox_df[tox_col] = tox_df[tox_col].astype(str).str.strip()

                            tox_df = tox_df[(tox_df[tox_pid_col] != "") & (tox_df[tox_pid_col] != "nan")]
                            tox_df = tox_df[(tox_df[tox_col] != "") & (tox_df[tox_col].str.lower() != "nan")]

                            tox_agg = (
                                tox_df.groupby(tox_pid_col)[tox_col]
                                .apply(lambda s: ", ".join(sorted(set(s.tolist()))))
                                .to_dict()
                            )

                            registered_df["TOXICITY"] = _clean_key_series(registered_df["PRODUCT ID"]).map(tox_agg).fillna("")
                            tox_matches = (registered_df["TOXICITY"] != "").sum()
                            print(f"Added 'TOXICITY' for {tox_matches} rows.")

                    except Exception as e:
                        print(f"Error adding TOXICITY: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        registered_df["TOXICITY"] = ""

                # Add PRODUCT USE as comma-separated list per PRODUCT ID from newest Dec_ProductData_ProductUse-*.csv
                print("\n" + "=" * 60)
                print("Adding PRODUCT USE column...")
                print("=" * 60)

                product_use_pattern = os.path.join(downloader.download_dir, "Dec_ProductData_ProductUse-*.csv")
                product_use_files = glob.glob(product_use_pattern)

                if not product_use_files:
                    print(f"Warning: No Dec_ProductData_ProductUse CSV file found in {downloader.download_dir}")
                    registered_df["PRODUCT USE"] = ""
                else:
                    newest_product_use_file = max(product_use_files, key=os.path.getmtime)
                    print(f"Using ProductUse lookup file: {os.path.basename(newest_product_use_file)}")

                    try:
                        use_df = pd.read_csv(newest_product_use_file)
                        print(f"Loaded {len(use_df)} rows from ProductUse file")

                        use_pid_col = _find_col(use_df, "PRODUCT ID", "PRODUCT_ID", "PRODUCTID")
                        use_col = _find_col(use_df, "PRODUCT USE", "PRODUCT_USE", "PRODUCTUSE")

                        if not use_pid_col or not use_col:
                            print("Warning: Missing required columns in ProductUse CSV; cannot add PRODUCT USE.")
                            print(f"Detected columns: product_id={use_pid_col}, product_use={use_col}")
                            registered_df["PRODUCT USE"] = ""
                        else:
                            use_df[use_pid_col] = _clean_key_series(use_df[use_pid_col])
                            use_df[use_col] = use_df[use_col].astype(str).str.strip()

                            use_df = use_df[(use_df[use_pid_col] != "") & (use_df[use_pid_col] != "nan")]
                            use_df = use_df[(use_df[use_col] != "") & (use_df[use_col].str.lower() != "nan")]

                            use_agg = (
                                use_df.groupby(use_pid_col)[use_col]
                                .apply(lambda s: ", ".join(sorted(set(s.tolist()))))
                                .to_dict()
                            )

                            registered_df["PRODUCT USE"] = _clean_key_series(registered_df["PRODUCT ID"]).map(use_agg).fillna("")
                            use_matches = (registered_df["PRODUCT USE"] != "").sum()
                            print(f"Added 'PRODUCT USE' for {use_matches} rows.")

                    except Exception as e:
                        print(f"Error adding PRODUCT USE: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        registered_df["PRODUCT USE"] = ""
                
                # Filter out certain PRODUCT TYPE values
                excluded_product_types = [
                    "ANTIMICROBIAL, DISINFECTANT",
                    "ANTIMICROBIAL, SANITIZER",
                    "ALGAECIDE, ANTIMICROBIAL, SANITIZER",
                    "ANTIMICROBIAL, DISINFECTANT, MILDEWSTATIC",
                    "SANITIZER",
                    "ALGAECIDE, ANTIMICROBIAL",
                    "DISINFECTANT",
                    "ANTIMICROBIAL",
                    "ALGAECIDE",
                    "DISINFECTANT, SANITIZER",
                    "WOOD PRESERVATIVE",
                    "ALGAECIDE, DISINFECTANT",
                    "ALGAECIDE, ANTIMICROBIAL, DISINFECTANT, MOLLUSCICIDE",
                    "ALGAECIDE, ANTIFOULANT",
                    "ANTIFOULANT",
                    "0",
                    "ANTIMICROBIAL, WOOD PRESERVATIVE",
                    "ALGAECIDE, SANITIZER",
                    "PISCICIDE",
                    "CONTRACEPTIVE"
                ]
                
                if "PRODUCT TYPE" in registered_df.columns:
                    # Filter out rows with excluded product types
                    rows_before = len(registered_df)
                    registered_df = registered_df[~registered_df["PRODUCT TYPE"].isin(excluded_product_types)]
                    rows_after = len(registered_df)
                    rows_removed = rows_before - rows_after
                    
                    print(f"\nFiltered out {rows_removed} rows with excluded PRODUCT TYPE values")
                    print(f"Number of rows after PRODUCT TYPE filtering: {len(registered_df)}")
                else:
                    print(f"\nWarning: 'PRODUCT TYPE' column not found. Skipping PRODUCT TYPE filter.")

                # Additional filter: keep only rows whose PRODUCT USE values are within the allowed set
                allowed_product_uses = {
                    "AGRICULTURAL",
                    "TURF",
                    "NURSERY",
                    "ORNAMENTAL",
                    "COMMERCIAL",
                    "GREENHOUSE",
                    "HEMP",
                    "CANNABIS",
                    "HEMP (EPA LABEL)",
                    "SEED TREATMENT",
                }

                def _split_product_uses(val) -> list[str]:
                    if pd.isna(val):
                        return []
                    parts = [p.strip() for p in str(val).split(",")]
                    # Drop empty and "nan" tokens
                    return [p for p in parts if p and p.lower() != "nan"]

                def _product_use_is_allowed(val) -> bool:
                    uses = _split_product_uses(val)
                    if not uses:
                        # Keep rows if PRODUCT USE is empty/missing
                        return True
                    # Keep rows if ANY of the uses are in the allowed list
                    return any(u in allowed_product_uses for u in uses)

                if "PRODUCT USE" in registered_df.columns:
                    rows_before = len(registered_df)
                    registered_df = registered_df[registered_df["PRODUCT USE"].apply(_product_use_is_allowed)]
                    rows_after = len(registered_df)
                    print(f"\nFiltered out {rows_before - rows_after} rows based on PRODUCT USE allowed list")
                    print(f"Number of rows after PRODUCT USE filtering: {len(registered_df)}")
                else:
                    print("\nWarning: 'PRODUCT USE' column not found. Skipping PRODUCT USE filter.")
                
                # Add "is_PDF_downloaded" column using improved matching logic
                print("\n" + "=" * 60)
                print("Checking for downloaded PDFs...")
                print("=" * 60)
                
                # Get the path to PDFs directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                pdf_dir = os.path.join(script_dir, "PDFs")
                pdf_dir = os.path.normpath(pdf_dir)
                
                if not os.path.exists(pdf_dir):
                    print(f"Warning: PDF directory not found: {pdf_dir}")
                    registered_df["is_PDF_downloaded"] = "FALSE"
                    registered_df["pdf_filename"] = ""
                else:
                    # Get all files in the directory
                    all_files = [f for f in os.listdir(pdf_dir) if os.path.isfile(os.path.join(pdf_dir, f))]
                    print(f"Found {len(all_files)} total files in {pdf_dir}")
                    
                    # Create DataFrame with filenames
                    files_df = pd.DataFrame(all_files, columns=["File_Name"])
                    
                    # Store original filename before processing
                    files_df["Original_File_Name"] = files_df["File_Name"]
                    
                    # Filter to only PDF files
                    files_df = files_df[files_df["File_Name"].str.lower().str.contains(".pdf", na=False)].reset_index(drop=True)
                    print(f"Found {len(files_df)} PDF files")
                    
                    # Filter to only files with "PRIMARY_LABEL" in name
                    files_df = files_df[files_df["File_Name"].str.contains("PRIMARY_LABEL", case=False, na=False)].reset_index(drop=True)
                    print(f"Found {len(files_df)} PDF files with 'PRIMARY_LABEL' in name")
                    
                    # Clean the filenames: remove "_PRIMARY_LABEL" and everything after, then remove underscores
                    files_df["File_Name"] = files_df["File_Name"].str.replace(r"_PRIMARY_LABEL.*", "", regex=True)
                    files_df["File_Name"] = files_df["File_Name"].str.replace("_", "", regex=False)
                    
                    # Additional cleaning: lowercase, remove "and", remove spaces
                    files_df["File_Name"] = files_df["File_Name"].str.lower()
                    files_df["File_Name"] = files_df["File_Name"].str.replace("and", "", regex=False)
                    files_df["File_Name"] = files_df["File_Name"].str.replace(" ", "", regex=False)
                    
                    # Create mapping from cleaned pattern to original filename(s)
                    # Handle multiple files that might match the same cleaned pattern
                    pattern_to_filename = {}
                    for _, row in files_df.iterrows():
                        cleaned_pattern = row["File_Name"]
                        original_filename = row["Original_File_Name"]
                        if cleaned_pattern not in pattern_to_filename:
                            pattern_to_filename[cleaned_pattern] = []
                        pattern_to_filename[cleaned_pattern].append(original_filename)
                    
                    # Create set of cleaned filenames for fast lookup
                    pdf_patterns = set(files_df["File_Name"].tolist())
                    print(f"Created {len(pdf_patterns)} unique cleaned PDF patterns")
                    
                    # Create concat_sub column for products: ProductName + Product No.
                    registered_df["concat_sub"] = registered_df["ProductName"].astype(str) + registered_df["Product No."].astype(str)
                    
                    # Clean the concat_sub column: lowercase, remove spaces, "/", "&", "and"
                    registered_df["concat_sub"] = (
                        registered_df["concat_sub"]
                        .str.lower()
                        .str.replace(" ", "", regex=False)
                        .str.replace("/", "", regex=False)
                        .str.replace("&", "", regex=False)
                        .str.replace("and", "", regex=False)
                    )
                    
                    # Check if concat_sub matches any cleaned PDF filename and get the actual filename
                    def get_pdf_filename(cleaned_pattern):
                        """Get the PDF filename for a matched pattern. If multiple matches, take the first one."""
                        if cleaned_pattern in pattern_to_filename:
                            # If multiple files match, take the first one
                            return pattern_to_filename[cleaned_pattern][0]
                        return ""
                    
                    # Check matches and get filenames
                    registered_df["is_PDF_downloaded"] = registered_df["concat_sub"].isin(pdf_patterns).map({True: "TRUE", False: "FALSE"})
                    registered_df["pdf_filename"] = registered_df["concat_sub"].apply(
                        lambda x: get_pdf_filename(x) if x in pdf_patterns else ""
                    )
                    
                    # Count matches
                    pdf_matches = (registered_df["is_PDF_downloaded"] == "TRUE").sum()
                    pdf_not_downloaded = (registered_df["is_PDF_downloaded"] == "FALSE").sum()
                    print(f"Found PDF matches for {pdf_matches} out of {len(registered_df)} products ({pdf_matches/len(registered_df)*100:.1f}%)")
                    print(f"Products not yet downloaded: {pdf_not_downloaded}")
                    
                    # Drop the concat_sub column as it was only used for matching
                    registered_df = registered_df.drop(columns=["concat_sub"])
                
                # Save the filtered CSV as current_products_edited.csv
                output_path = os.path.join(downloader.download_dir, "current_products_edited.csv")
                registered_df.to_csv(output_path, index=False)
                print(f"\nFiltered CSV saved to: {output_path}")
                print(f"Saved {len(registered_df)} rows (filtered by REGISTERED status and PRODUCT TYPE)")
            else:
                print(f"\nWarning: 'Registration Status' column not found.")
                print(f"Available columns: {list(current_products_df.columns)}")
                
        except Exception as e:
            print(f"Error analyzing CSV file: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return 0
    else:
        print("Download failed. Check the log file for details.")
        return 1


if __name__ == "__main__":
    exit(main())


