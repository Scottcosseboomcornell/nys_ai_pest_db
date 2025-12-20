#!/usr/bin/env python3
"""
NYSPAD Search-Based Product Scraper with Parallel Processing
Searches for specific products by name using the NYSPAD search interface
Supports multiple concurrent browser instances for faster processing
"""

import os
import time
import logging
import glob
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Dict, Optional, List
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class NewNYSPADScraper:
    def __init__(self, download_dir: str = "PDFs", 
                 csv_path: str = "current_products_edited.csv",
                 headless: bool = True, delay: float = 2.0):
        """
        Initialize the NYSPAD bulk scraper
        
        Args:
            download_dir: Directory to save downloaded PDFs and text files
            csv_path: Path to current_products_edited.csv
            headless: Run browser in headless mode
            delay: Delay between requests to be respectful
        """
        self.download_dir = download_dir
        self.delay = delay
        self.base_url = "https://extapps.dec.ny.gov/nyspad/products"  # Go directly to products page
        self.csv_path = csv_path
        
        # Create download directory
        os.makedirs(download_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('new_NY_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Setup Chrome options
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        
        # Set download preferences
        prefs = {
            "download.default_directory": os.path.abspath(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        self.chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = None
        
        # Load CSV to get products that need to be scraped
        self.products_to_scrape = []
        self._load_products_needing_scrape()
    
    def _load_products_needing_scrape(self):
        """Load products from CSV that have is_PDF_downloaded = FALSE"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Use nyspad_csv_downloads directory for CSV files
            csv_dir = os.path.join(script_dir, "nyspad_csv_downloads")
            os.makedirs(csv_dir, exist_ok=True)
            # If csv_path is just a filename, look in nyspad_csv_downloads; otherwise use as-is
            if os.path.dirname(self.csv_path) == "":
                csv_full_path = os.path.join(csv_dir, self.csv_path)
            else:
            csv_full_path = os.path.join(script_dir, self.csv_path)
            
            if not os.path.exists(csv_full_path):
                self.logger.warning(f"CSV file not found: {csv_full_path}")
                return
            
            df = pd.read_csv(csv_full_path, low_memory=False)
            
            if "ProductName" in df.columns and "is_PDF_downloaded" in df.columns:
                # Filter for products where PDF is not downloaded
                needs_download = df[df["is_PDF_downloaded"] == False].copy()
                
                # Also handle string 'FALSE' values
                if needs_download.empty:
                    needs_download = df[df["is_PDF_downloaded"].astype(str).str.upper() == 'FALSE'].copy()
                
                # Store product info
                for _, row in needs_download.iterrows():
                    product_info = {
                        'product_name': str(row["ProductName"]).strip(),
                        'product_no': str(row.get("Product No.", "")).strip() if "Product No." in row else None,
                        'epa_reg': str(row.get("EPA Reg. No.", "")).strip() if "EPA Reg. No." in row else None,
                    }
                    self.products_to_scrape.append(product_info)
                
                self.logger.info(f"Loaded {len(self.products_to_scrape)} products that need PDF download")
            else:
                self.logger.error("CSV missing required columns: ProductName or is_PDF_downloaded")
                
        except Exception as e:
            self.logger.error(f"Error loading CSV: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.driver = webdriver.Chrome(options=self.chrome_options)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.driver:
            self.driver.quit()
    
    def _handle_notice_modal(self, driver=None):
        """
        Handle the Notice modal that appears on first visit
        
        Args:
            driver: Optional webdriver instance. If None, uses driver_to_use
        """
        driver_to_use = driver if driver is not None else driver_to_use
        
        try:
            # Wait a bit for modal to appear
            time.sleep(2)
            
            # Look for the Notice modal
            notice_selectors = [
                "//div[contains(text(), 'Notice')]",
                "//h1[contains(text(), 'Notice')]",
                "//h2[contains(text(), 'Notice')]",
                "//h3[contains(text(), 'Notice')]",
                ".modal:contains('Notice')",
                "[class*='modal']:contains('Notice')"
            ]
            
            notice_modal = None
            for selector in notice_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        notice_modal = driver_to_use.find_element(By.XPATH, selector)
                    else:
                        # CSS selector
                        notice_modal = driver_to_use.find_element(By.CSS_SELECTOR, selector)
                    
                    if notice_modal and notice_modal.is_displayed():
                        self.logger.info("Found Notice modal")
                        break
                except:
                    continue
            
            if notice_modal:
                # Look for the Continue button
                continue_selectors = [
                    "//button[contains(text(), 'Continue')]",
                    "//input[@value='Continue']",
                    "//a[contains(text(), 'Continue')]",
                    "button:contains('Continue')",
                    "input[value='Continue']",
                    "a:contains('Continue')"
                ]
                
                continue_button = None
                for selector in continue_selectors:
                    try:
                        if selector.startswith("//"):
                            # XPath selector
                            continue_button = driver_to_use.find_element(By.XPATH, selector)
                        else:
                            # CSS selector
                            continue_button = driver_to_use.find_element(By.CSS_SELECTOR, selector)
                        
                        if continue_button and continue_button.is_displayed() and continue_button.is_enabled():
                            self.logger.info("Found Continue button, clicking to dismiss modal")
                            driver_to_use.execute_script("arguments[0].click();", continue_button)
                            time.sleep(2)  # Wait for modal to close
                            break
                    except:
                        continue
                
                if not continue_button:
                    self.logger.warning("Found Notice modal but could not find Continue button")
            else:
                self.logger.debug("No Notice modal found")
                
        except Exception as e:
            self.logger.debug(f"Error handling Notice modal: {e}")
    
    def navigate_to_products_list(self):
        """Navigate to the products list page by going directly to products URL and clicking Search"""
        try:
            self.logger.info("Navigating to NYSPAD products page...")
            self.driver.get(self.base_url)  # Goes directly to /nyspad/products
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Handle notice modal (must be done before trying to find Search button)
            self._handle_notice_modal()
            
            # Wait for any overlays to disappear
            try:
                WebDriverWait(self.driver, 5).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".wicket-mask-dark, .loading, .overlay"))
                )
            except TimeoutException:
                self.logger.info("Overlay still present, continuing anyway")
            
            # Find and click the Search button (same approach as old scraper)
            search_button = None
            button_selectors = [
                "button.searchButton.dec-button",  # NYSPAD search button
                "input[type='submit']",
                "button[type='submit']",
                "//button[contains(text(), 'Search')]",
                "//input[@value='Search']",
                "//input[@value*='Search']",
                ".search-button",
                "#search-button"
            ]
            
            for selector in button_selectors:
                try:
                    if selector.startswith("//"):
                        search_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        search_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if search_button and search_button.is_displayed() and search_button.is_enabled():
                        self.logger.info(f"Found Search button with selector: {selector}")
                        break
                except:
                    continue
            
            if search_button:
                # Scroll to button and click it
                self.driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", search_button)
                self.logger.info("Clicked Search button to show unfiltered product list")
                time.sleep(3)  # Wait for page to respond
                
                # Handle notice modal again (it may appear after clicking Search)
                self._handle_notice_modal()
                
                time.sleep(2)  # Additional wait for results to load
                return True
            else:
                self.logger.error("Could not find Search button")
                # Log page structure for debugging
                self.logger.debug(f"Page title: {self.driver.title}")
                self.logger.debug(f"Page URL: {self.driver.current_url}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to products list: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def search_product_by_name(self, product_name: str) -> bool:
        """
        Search for a specific product by name using the search interface
        
        Args:
            product_name: Name of the product to search for
            
        Returns:
            True if search was successful, False otherwise
        """
        try:
            self.logger.info(f"Searching for product: {product_name}")
            
            # Navigate to products page
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Handle notice modal
            self._handle_notice_modal()
            
            # Find the product name search input field
            search_input = None
            input_selectors = [
                "input[name='searchFormPanelContainer:searchForm:form:productName']",  # NYSPAD product name field
                "input[placeholder*='Product Name']",
                "input[placeholder*='product name']",
            ]
            
            for selector in input_selectors:
                try:
                    search_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    self.logger.info(f"Found product name search input with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not search_input:
                self.logger.error("Could not find product name search input field")
                return False
            
            # Enter the product name
            self.driver.execute_script("arguments[0].scrollIntoView(true);", search_input)
            time.sleep(1)
            self.driver.execute_script("arguments[0].value = '';", search_input)
            self.driver.execute_script("arguments[0].value = arguments[1];", search_input, product_name)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", search_input)
            
            self.logger.info(f"Entered product name: {product_name}")
            
            # Find and click the Search button
            search_button = None
            button_selectors = [
                "button.searchButton.dec-button",  # NYSPAD search button
                "//button[contains(text(), 'Search')]",
                "input[type='submit'][value='Search']",
            ]
            
            for selector in button_selectors:
                try:
                    if selector.startswith("//"):
                        search_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        search_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if search_button and search_button.is_displayed() and search_button.is_enabled():
                        self.logger.info(f"Found Search button with selector: {selector}")
                        break
                except:
                    continue
            
            if not search_button:
                self.logger.error("Could not find Search button")
                return False
            
            # Click search button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", search_button)
            self.logger.info("Clicked Search button")
            
            # Wait for search results to load
            time.sleep(10)  # Wait 10 seconds for search results
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error searching for product {product_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_products_from_page(self) -> List[Dict]:
        """Extract product information from the current page"""
        products = []
        
        try:
            # Find all "More" buttons - each represents a product
            more_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'More')] | //a[contains(text(), 'More')]")
            
            self.logger.info(f"Found {len(more_buttons)} 'More' buttons on current page")
            
            # For each More button, extract the product name from the row
            for i, more_button in enumerate(more_buttons):
                try:
                    # Find the parent row/container
                    parent_row = more_button.find_element(By.XPATH, "./ancestor::tr | ./ancestor::div[contains(@class, 'row')] | ./ancestor::*[contains(@class, 'result')] | ..")
                    
                    # Get all text from the row
                    row_text = parent_row.text
                    
                    # Extract product name (first line before "More")
                    lines = row_text.split('\n')
                    product_name = None
                    
                    for line in lines:
                        line = line.strip()
                        if line and 'More' not in line and 'EPA Reg. No.' not in line:
                            # This is likely the product name
                            product_name = line
                            break
                    
                    # Also try to extract EPA Reg. No. and Product No.
                    epa_reg_match = re.search(r'EPA Reg\. No\.\s*([\d-]+)', row_text)
                    epa_reg = epa_reg_match.group(1) if epa_reg_match else None
                    
                    # Use full EPA Reg. No. as Product No. (matches naming convention)
                    product_no = epa_reg if epa_reg else None
                    
                    if product_name:
                        products.append({
                            'product_name': product_name,
                            'epa_reg': epa_reg,
                            'product_no': product_no,
                            'more_button': more_button,
                            'index': i,  # Store the index for re-finding the button later
                            'row_text': row_text
                        })
                        self.logger.debug(f"Extracted product {i+1}: {product_name}")
                    
                except Exception as e:
                    self.logger.warning(f"Error extracting product {i+1}: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(products)} products from current page")
            return products
            
        except Exception as e:
            self.logger.error(f"Error extracting products from page: {e}")
            return []
    
    def _get_more_button_by_index(self, index: int, driver=None):
        """
        Get the Nth 'More' button on the current page (0-based index).
        
        Args:
            index: The index of the More button to find
            driver: Optional webdriver instance. If None, uses self.driver
        """
        driver_to_use = driver if driver is not None else self.driver
        
        try:
            more_buttons = driver_to_use.find_elements(
                By.XPATH,
                "//button[contains(text(), 'More')] | //a[contains(text(), 'More')]"
            )
            if 0 <= index < len(more_buttons):
                return more_buttons[index]
            self.logger.warning(
                f"Requested More button index {index} but found {len(more_buttons)} button(s)"
            )
            return None
        except Exception as e:
            self.logger.error(f"Error finding More button at index {index}: {e}")
            return None
    
    def process_product(self, product: Dict, driver=None) -> bool:
        """
        Process a single product: check CSV status and download if needed
        
        Args:
            product: Product dictionary with product information
            driver: Optional webdriver instance. If None, uses self.driver
        
        Returns:
            True if successful, False otherwise
        """
        # Use provided driver or fall back to self.driver
        driver_to_use = driver if driver is not None else self.driver
        
        product_name = product['product_name']
        
        try:
            # Check filesystem directly to see if PDF already exists
            safe_name = product_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("&", "and")
            product_no = product.get('product_no', 'unknown')
            pdf_pattern = f"{safe_name}_{product_no}_PRIMARY_LABEL_*.pdf"
            
            # Check if any file matching the pattern exists
            matching_files = glob.glob(os.path.join(self.download_dir, pdf_pattern))
            if matching_files:
                self.logger.info(f"SKIP: {product_name} (PDF already exists in filesystem: {os.path.basename(matching_files[0])})")
                return True
            
            self.logger.info(f"PROCESSING: {product_name} - PDF not downloaded, scraping...")
            
            # Re-find and click the More button (refresh the element reference to avoid stale elements)
            more_button_index = product.get('index', 0)
            more_button = self._get_more_button_by_index(more_button_index, driver_to_use)
            
            if not more_button:
                self.logger.error(f"Could not find More button for {product_name}")
                return False
            
            try:
                # Scroll into view and wait a moment
                driver_to_use.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
                time.sleep(2)
                
                # Log the button state before clicking
                self.logger.info(f"More button found - Displayed: {more_button.is_displayed()}, Enabled: {more_button.is_enabled()}")
                
                # Try regular click first
                try:
                    more_button.click()
                    self.logger.info(f"Clicked More button for {product_name} (regular click), waiting for modal...")
                except Exception as click_error:
                    # If regular click fails, use JavaScript click
                    self.logger.warning(f"Regular click failed: {click_error}, trying JS click...")
                    driver_to_use.execute_script("arguments[0].click();", more_button)
                    self.logger.info(f"Clicked More button for {product_name} (JS click), waiting for modal...")
                
                # Wait longer for slow website to load modal
                self.logger.info("Waiting 8 seconds for modal to appear...")
                time.sleep(8)
                
                # Debug: Check what's on the page
                try:
                    modals = driver_to_use.find_elements(By.CSS_SELECTOR, ".modal, .modal-content, .wicket-modal, [class*='modal']")
                    self.logger.info(f"Found {len(modals)} potential modal elements on page")
                    for i, modal in enumerate(modals[:3]):  # Check first 3
                        self.logger.info(f"  Modal {i+1}: Displayed={modal.is_displayed()}, Class={modal.get_attribute('class')}")
                except Exception as debug_e:
                    self.logger.debug(f"Debug check failed: {debug_e}")
                
            except Exception as e:
                self.logger.error(f"Error clicking More button for {product_name}: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # Extract modal information
            modal_text = self._extract_modal_information(driver_to_use)
            
            # Save modal information to text file
            safe_name = product_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("&", "and")
            product_no = product.get('product_no', 'unknown')
            
            # Save text file
            txt_filename = f"{safe_name}_{product_no}_PRIMARY_LABEL_Info.txt"
            txt_filepath = os.path.join(self.download_dir, txt_filename)
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"Product Information for: {product_name}\n")
                f.write("=" * 50 + "\n\n")
                f.write(modal_text)
            self.logger.info(f"Saved text file: {txt_filename}")
            
            # Extract document number from modal text to ensure we're getting fresh data
            doc_number_from_text = self._extract_first_doc_number_from_text(modal_text)
            if doc_number_from_text:
                self.logger.info(f"Extracted document number from modal text: {doc_number_from_text}")
            
            # Download PDF if available - use the doc number from text to ensure correctness
            success = self._download_first_pdf_from_modal(safe_name, product_no, doc_number_from_text, driver_to_use)
            if success:
                self.logger.info(f"Successfully downloaded PDF with document number: {doc_number_from_text}")
            else:
                self.logger.warning(f"No PDF link found or download failed for {product_name}")
            
            # Close modal and wait for it to fully close before continuing
            self.logger.info("Closing modal...")
            modal_closed = self._close_modal(driver_to_use)
            if modal_closed:
                self.logger.info("Modal closed successfully")
            else:
                self.logger.warning("Modal may not have closed properly")
            time.sleep(3)  # Extra wait to ensure modal is fully closed and DOM is stable
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing product {product_name}: {e}")
            # Try to close modal if it's still open
            try:
                self.logger.info("Attempting to close modal after error...")
                self._close_modal()
                time.sleep(3)  # Extra wait after error recovery
            except:
                pass
            return False
    
    def _extract_modal_information(self, driver=None) -> str:
        """
        Extract all product information from the modal view
        
        Args:
            driver: Optional webdriver instance. If None, uses self.driver
        """
        driver_to_use = driver if driver is not None else self.driver
        
        try:
            # Wait at least 10 seconds for modal to appear (website is slow)
            self.logger.info("Waiting for modal to appear...")
            WebDriverWait(driver_to_use, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".modal-content, .wicket-modal"))
            )
            
            # Additional wait for content to load
            time.sleep(2)
            
            modal_content = driver_to_use.find_element(By.CSS_SELECTOR, ".modal-content, .wicket-modal")
            modal_text = modal_content.text
            
            lines = modal_text.split('\n')
            formatted_lines = [line.strip() for line in lines if line.strip()]
            formatted_text = '\n'.join(formatted_lines)
            
            return formatted_text
            
        except TimeoutException:
            self.logger.warning("Modal did not appear within timeout, trying to extract anyway...")
            # Try to extract anyway in case modal is there but selector didn't match
            try:
                modal_content = driver_to_use.find_element(By.CSS_SELECTOR, ".modal-content, .wicket-modal, .modal")
                modal_text = modal_content.text
                lines = modal_text.split('\n')
                formatted_lines = [line.strip() for line in lines if line.strip()]
                formatted_text = '\n'.join(formatted_lines)
                return formatted_text
            except:
                return "Error: Could not extract modal information - modal did not appear"
        except Exception as e:
            self.logger.error(f"Error extracting modal information: {e}")
            return "Error: Could not extract modal information"
    
    def _extract_first_doc_number_from_text(self, modal_text: str) -> Optional[str]:
        """Extract the first document number from the modal text"""
        import re
        try:
            # Look for patterns like "PRIMARY LABEL" followed by date and number
            # Or just find numbers that look like document numbers (typically 6 digits)
            # Common pattern in the text: "PRIMARY LABEL    02/11/2009    517537"
            
            # Try to find the first document number after "PRIMARY LABEL"
            match = re.search(r'PRIMARY\s+LABEL\s+\d{2}/\d{2}/\d{4}\s+(\d{5,7})', modal_text)
            if match:
                doc_number = match.group(1)
                self.logger.info(f"Found document number in modal text: {doc_number}")
                return doc_number
            
            # Fallback: look for standalone 6-digit numbers (typical doc number format)
            matches = re.findall(r'\b(\d{6})\b', modal_text)
            if matches:
                doc_number = matches[0]  # Take the first one
                self.logger.info(f"Found potential document number in modal text: {doc_number}")
                return doc_number
                
            self.logger.warning("Could not extract document number from modal text")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting document number from text: {e}")
            return None
    
    def _download_first_pdf_from_modal(self, safe_product_name: str, product_no: str, expected_doc_number: Optional[str] = None, driver=None) -> bool:
        """
        Find the first PDF link in the modal and download it directly
        
        Args:
            safe_product_name: Product name safe for filenames
            product_no: Product number
            expected_doc_number: Expected document number (optional)
            driver: Optional webdriver instance. If None, uses driver_to_use
        """
        driver_to_use = driver if driver is not None else driver_to_use
        
        try:
            # Wait for modal content to load
            self.logger.info("Waiting for modal content to load...")
            WebDriverWait(driver_to_use, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".modal, .modal-dialog, [class*='modal']"))
            )
            time.sleep(3)  # Increased buffer for table rendering and to ensure modal is fully refreshed

            # If we have an expected doc number from the text, try to find that specific link first
            if expected_doc_number:
                self.logger.info(f"*** Looking for specific document number from modal text: {expected_doc_number} ***")
                try:
                    # Try to find the link by the exact document number text
                    specific_link = driver_to_use.find_element(By.XPATH, f"//a[normalize-space(text())='{expected_doc_number}']")
                    doc_number = expected_doc_number
                    self.logger.info(f"*** Found matching document link with number: {doc_number} ***")
                    
                    # Scroll into view
                    driver_to_use.execute_script("arguments[0].scrollIntoView({block: 'center'});", specific_link)
                    time.sleep(1)
                    
                    # Track files before clicking
                    initial_files = set(os.listdir(self.download_dir))
                    
                    # Click the link using JavaScript to avoid interception
                    self.logger.info(f"*** Clicking document number: {doc_number} ***")
                    driver_to_use.execute_script("arguments[0].click();", specific_link)
                    
                    # Wait for download
                    pdf_filename = f"{safe_product_name}_{product_no}_PRIMARY_LABEL_{doc_number}.pdf"
                    max_wait = 30
                    wait_time = 0
                    
                    while wait_time < max_wait:
                        time.sleep(1)
                        wait_time += 1
                        
                        current_files = set(os.listdir(self.download_dir))
                        new_files = current_files - initial_files
                        
                        for new_file in new_files:
                            if new_file.endswith('.pdf') and not new_file.endswith('.crdownload'):
                                old_path = os.path.join(self.download_dir, new_file)
                                new_path = os.path.join(self.download_dir, pdf_filename)
                                
                                if old_path != new_path:
                                    if os.path.exists(new_path):
                                        os.remove(new_path)  # Remove if exists
                                    os.rename(old_path, new_path)
                                    self.logger.info(f"Renamed {new_file} to {pdf_filename}")
                                
                                return True
                    
                    self.logger.warning(f"Download may not have completed for document: {doc_number}")
                    return False
                    
                except Exception as e:
                    self.logger.warning(f"Could not find specific document {expected_doc_number}, will try table approach: {e}")

            # Fallback: Find the NYS Labels/Documents table and get first link
            try:
                document_table = driver_to_use.find_element(
                    By.XPATH,
                    "//table[.//th[contains(normalize-space(.), 'Label/Document No.')]]"
                )
                self.logger.info("Found NYS Labels/Documents table")
            except Exception as e:
                self.logger.error(f"Could not find NYS Labels/Documents table: {e}")
                return False

            # Get the first data row's document number link (3rd column: Label/Document No.)
            try:
                first_link = document_table.find_element(
                    By.XPATH,
                    ".//tr[td][1]/td[3]//a"
                )
                doc_number = first_link.text.strip()
                self.logger.info(f"*** Found first document link in table with number: {doc_number} ***")
                
                # Log if it doesn't match expected (but proceed with table value)
                if expected_doc_number and doc_number != expected_doc_number:
                    self.logger.warning(f"*** Document number from text ({expected_doc_number}) differs from table ({doc_number}). Using table value. ***")
                
                # Scroll into view
                driver_to_use.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_link)
                time.sleep(1)
                
                # Track files before clicking
                initial_files = set(os.listdir(self.download_dir))
                
                # Click the link using JavaScript to avoid interception
                self.logger.info(f"*** Clicking document number: {doc_number} ***")
                driver_to_use.execute_script("arguments[0].click();", first_link)
                
                # Wait for download
                pdf_filename = f"{safe_product_name}_{product_no}_PRIMARY_LABEL_{doc_number}.pdf"
                max_wait = 30
                wait_time = 0
                
                while wait_time < max_wait:
                    time.sleep(1)
                    wait_time += 1
                    
                    current_files = set(os.listdir(self.download_dir))
                    new_files = current_files - initial_files
                    
                    for new_file in new_files:
                        if new_file.endswith('.pdf') and not new_file.endswith('.crdownload'):
                            old_path = os.path.join(self.download_dir, new_file)
                            new_path = os.path.join(self.download_dir, pdf_filename)
                            
                            if old_path != new_path:
                                if os.path.exists(new_path):
                                    os.remove(new_path)  # Remove if exists
                                os.rename(old_path, new_path)
                                self.logger.info(f"Renamed {new_file} to {pdf_filename}")
                            
                            return True
                
                self.logger.warning(f"Download may not have completed for document: {doc_number}")
                return False
                
            except Exception as e:
                self.logger.error(f"Could not find or click first document link in table: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error downloading PDF from modal: {e}")
            return False
    
    def _close_modal(self, driver=None) -> bool:
        """
        Close the modal by clicking the X button in the top right
        
        Args:
            driver: Optional webdriver instance. If None, uses self.driver
        
        Returns:
            True if modal was closed successfully, False otherwise
        """
        driver_to_use = driver if driver is not None else self.driver
        
        try:
            from selenium.webdriver.common.keys import Keys
            
            # First, try pressing Escape key (most reliable)
            driver_to_use.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            self.logger.info("Attempted to close modal using Escape key")
            time.sleep(2)
            
            # Check if modal is still visible
            try:
                modal_elements = driver_to_use.find_elements(By.CSS_SELECTOR, ".modal, .modal-dialog, [class*='modal'], .wicket-modal")
                if not modal_elements or not any(el.is_displayed() for el in modal_elements):
                    self.logger.info("Modal closed successfully with Escape key")
                    return True
            except:
                pass
            
            # If Escape didn't work, try clicking close buttons
            close_button_selectors = [
                "//button[contains(@class, 'close')]",
                "//button[contains(@aria-label, 'Close')]",
                "//button[contains(@title, 'Close')]",
                "//*[contains(@class, 'close') and (self::button or self::a)]",
                "//button[text()='×']",
                "//a[text()='×']",
                "//*[@class='modal-header']//button",
                "//*[@class='modal-header']//a",
                "//button[contains(text(), 'Close')]",
            ]
            
            for selector in close_button_selectors:
                try:
                    close_buttons = driver_to_use.find_elements(By.XPATH, selector)
                    for close_button in close_buttons:
                        if close_button.is_displayed() and close_button.is_enabled():
                            driver_to_use.execute_script("arguments[0].click();", close_button)
                            self.logger.info(f"Successfully closed modal using selector: {selector}")
                            time.sleep(2)
                            return True
                except:
                    continue
            
            # As a last resort, try clicking the modal backdrop
            try:
                # Click on the modal backdrop/overlay
                backdrop = driver_to_use.find_element(By.CSS_SELECTOR, ".modal-backdrop, .wicket-mask")
                if backdrop.is_displayed():
                    driver_to_use.execute_script("arguments[0].click();", backdrop)
                    self.logger.info("Closed modal by clicking backdrop")
                    time.sleep(2)
                    return True
            except:
                pass
            
            # If all else fails, try multiple Escape presses
            for _ in range(3):
                driver_to_use.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            
            self.logger.warning("Modal may still be open after all close attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing modal: {e}")
            return False
    
    def go_to_next_page(self) -> bool:
        """Navigate to the next page of results"""
        try:
            # Wait a moment for the page to stabilize
            time.sleep(2)
            
            # Look for "Next" button with multiple strategies
            next_button = None
            
            # XPath selectors to find Next button
            next_selectors = [
                "//a[normalize-space(text())='Next']",
                "//a[contains(text(), 'Next') and not(contains(@class, 'disabled'))]",
                "//button[normalize-space(text())='Next']",
                "//a[contains(text(), 'Next')]",
                "//button[contains(text(), 'Next')]",
                "//a[@title='Next']",
                "//a[contains(@class, 'next') and not(contains(@class, 'disabled'))]",
                "//button[contains(@class, 'next') and not(contains(@class, 'disabled'))]",
            ]
            
            self.logger.info("Searching for Next button...")
            
            # Debug: Print all links on page that contain "Next" or "Previous"
            try:
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                nav_links = [link for link in all_links if "next" in link.text.lower() or "previous" in link.text.lower()]
                self.logger.info(f"Found {len(nav_links)} navigation-related links:")
                for link in nav_links:
                    self.logger.info(f"  - Text: '{link.text}', Displayed: {link.is_displayed()}, Enabled: {link.is_enabled()}, Classes: {link.get_attribute('class')}")
            except Exception as e:
                self.logger.debug(f"Could not list navigation links: {e}")
            
            for selector in next_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    self.logger.debug(f"Selector '{selector}' found {len(elements)} element(s)")
                    
                    for element in elements:
                        try:
                            # Check if element is actually visible and clickable
                            if element.is_displayed():
                                element_text = element.text.strip()
                                self.logger.info(f"Found potential Next button: text='{element_text}', displayed={element.is_displayed()}, enabled={element.is_enabled()}")
                                
                                # Scroll into view
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(1)
                                
                                # Try to click
                                try:
                                    element.click()
                                    self.logger.info("Clicked Next button (regular click), waiting for page to load...")
                                except:
                                    # Fallback to JavaScript click
                                    self.driver.execute_script("arguments[0].click();", element)
                                    self.logger.info("Clicked Next button (JS click), waiting for page to load...")
                                
                                time.sleep(15)  # Wait 10 seconds for slow website to load next page
                                return True
                        except Exception as e:
                            self.logger.debug(f"Element not clickable: {e}")
                            continue
                except Exception as e:
                    self.logger.debug(f"Selector '{selector}' failed: {e}")
                    continue
            
            self.logger.info("No Next button found - reached last page")
            return False
            
        except Exception as e:
            self.logger.error(f"Error going to next page: {e}")
            return False
    
    def _scrape_single_product_wrapper(self, product_info: Dict, index: int, total: int) -> bool:
        """
        Wrapper method to scrape a single product in a separate browser instance
        This method creates its own driver and handles the complete search/scrape cycle
        
        Args:
            product_info: Dictionary with 'product_name' and 'product_no'
            index: Current product index (for logging)
            total: Total number of products (for logging)
            
        Returns:
            True if successful, False otherwise
        """
        driver = None
        product_name = product_info['product_name']
        product_no = product_info['product_no']
        
        try:
            self.logger.info(f"\n[Browser {index}/{total}] Starting scrape for: {product_name}")
            
            # Create a new driver for this thread
            driver = webdriver.Chrome(options=self.chrome_options)
            
            # Navigate to products page
            driver.get(self.base_url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)
            
            # Handle the Notice modal if it appears
            self._handle_notice_modal(driver)
            
            # Find the Product Name search input field
            search_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='searchFormPanelContainer:searchForm:form:productName']"))
            )
            
            self.logger.info(f"[Browser {index}/{total}] Found search input for {product_name}")
            driver.execute_script("arguments[0].scrollIntoView(true);", search_input)
            time.sleep(0.5)
            driver.execute_script("arguments[0].value = '';", search_input)
            driver.execute_script("arguments[0].value = arguments[1];", search_input, product_name)
            
            # Click the Search button
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.searchButton.dec-button"))
            )
            self.logger.info(f"[Browser {index}/{total}] Clicking Search button...")
            driver.execute_script("arguments[0].click();", search_button)
            time.sleep(5)  # Wait for search results
            
            # Handle notice modal again (it may appear after clicking Search)
            self._handle_notice_modal(driver)
            
            # Find all "More" buttons - each represents a product
            more_buttons = WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'More')] | //a[contains(text(), 'More')]"))
            )
            
            if not more_buttons:
                self.logger.warning(f"[Browser {index}/{total}] No 'More' button found for: {product_name}")
                return False
            
            # Get the first result (most relevant)
            first_more_button = more_buttons[0]
            parent_row = first_more_button.find_element(By.XPATH, "./ancestor::tr | ./ancestor::div[contains(@class, 'row')] | ./ancestor::*[contains(@class, 'result')] | ..")
            row_text = parent_row.text
            
            # Create product dict for process_product
            product_data = {
                'product_name': product_name,
                'product_no': product_no,
                'more_button': first_more_button,
                'row_text': row_text,
                'index': 0
            }
            
            # Process this product using the current driver instance
            success = self.process_product(product_data, driver)
            
            if success:
                self.logger.info(f"[Browser {index}/{total}] ✓ Successfully scraped: {product_name}")
            else:
                self.logger.warning(f"[Browser {index}/{total}] ✗ Failed to scrape: {product_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"[Browser {index}/{total}] Error scraping {product_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                    self.logger.info(f"[Browser {index}/{total}] Closed browser for: {product_name}")
                except:
                    pass
    
    def scrape_products_from_csv(self, max_products: Optional[int] = None, max_workers: int = 6, start_delay: float = 10.0):
        """
        Scrape products from CSV using parallel browser instances
        
        Args:
            max_products: Maximum number of products to process (for testing)
            max_workers: Maximum number of concurrent browser instances (default: 6)
            start_delay: Minimum seconds between starting new browsers (default: 10.0)
        """
        try:
            if not self.products_to_scrape:
                self.logger.info("No products need to be scraped")
                return
            
            products_list = self.products_to_scrape[:max_products] if max_products else self.products_to_scrape
            total = len(products_list)
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Starting PARALLEL search-based scraping for {total} products")
            self.logger.info(f"Max concurrent browsers: {max_workers}")
            self.logger.info(f"Start delay between browsers: {start_delay}s")
            self.logger.info(f"{'='*60}\n")
            
            processed = 0
            failed = 0
            start_times = []  # Track when each browser was started
            start_lock = threading.Lock()  # Lock for thread-safe start time tracking
            
            def rate_limited_scrape(product_info, index):
                """Wrapper that enforces rate limiting before starting scrape"""
                with start_lock:
                    # Wait until at least start_delay seconds have passed since the last start
                    if start_times:
                        time_since_last_start = time.time() - start_times[-1]
                        if time_since_last_start < start_delay:
                            wait_time = start_delay - time_since_last_start
                            self.logger.info(f"[Browser {index}/{total}] Rate limiting: waiting {wait_time:.1f}s before starting...")
                            time.sleep(wait_time)
                    
                    start_times.append(time.time())
                    self.logger.info(f"[Browser {index}/{total}] Starting browser instance (Active: {threading.active_count()-1}/{max_workers})...")
                
                # Now actually scrape
                return self._scrape_single_product_wrapper(product_info, index, total)
            
            # Use ThreadPoolExecutor to manage concurrent browser instances
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(rate_limited_scrape, product_info, i): (product_info, i) 
                    for i, product_info in enumerate(products_list, 1)
                }
                
                # Process results as they complete
                for future in as_completed(futures):
                    product_info, index = futures[future]
                    try:
                        success = future.result()
                        if success:
                            processed += 1
                        else:
                            failed += 1
                    except Exception as e:
                        self.logger.error(f"[Browser {index}/{total}] Exception for {product_info['product_name']}: {e}")
                        failed += 1
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Parallel search-based scraping completed!")
            self.logger.info(f"Successfully processed: {processed}")
            self.logger.info(f"Failed: {failed}")
            self.logger.info(f"Total browsers used: {len(start_times)}")
            self.logger.info(f"{'='*60}")
            
        except Exception as e:
            self.logger.error(f"Error in scrape_products_from_csv: {e}")
            import traceback
            traceback.print_exc()
    
    def scrape_all_products(self, max_pages: Optional[int] = None):
        """Scrape all products from all pages"""
        try:
            # Navigate to products list
            if not self.navigate_to_products_list():
                self.logger.error("Failed to navigate to products list")
                return
            
            page_num = 1
            total_processed = 0
            total_skipped = 0
            
            while True:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Processing page {page_num}")
                self.logger.info(f"{'='*60}")
                
                # Extract products from current page
                products = self.extract_products_from_page()
                
                if not products:
                    self.logger.info("No products found on this page")
                    break

                # Process each product
                for i, product in enumerate(products, 1):
                    self.logger.info(f"\n--- Product {i}/{len(products)} on page {page_num} ---")
                    
                    # Check if already downloaded
                    product_name = product['product_name']
                    # Normalize product name by replacing spaces with underscores AND lowercase to match dictionary keys
                    product_name_normalized = product_name.replace(" ", "_").lower()
                    if product_name_normalized in self.pdf_status_dict and self.pdf_status_dict[product_name_normalized]:
                        total_skipped += 1
                        self.logger.info(f"SKIP: {product_name} (already downloaded)")
                        continue

                    # Re-locate the More button for this index to avoid stale element issues
                    more_button = self._get_more_button_by_index(i - 1)
                    if not more_button:
                        total_skipped += 1
                        self.logger.warning(f"Could not find 'More' button for {product_name}, skipping")
                        continue

                    product['more_button'] = more_button
                    
                    # Process the product
                    success = self.process_product(product)
                    if success:
                        total_processed += 1
                    
                    # Be respectful with delays
                    time.sleep(self.delay)
                
                # Check if we should continue
                if max_pages and page_num >= max_pages:
                    self.logger.info(f"Reached maximum page limit ({max_pages})")
                    break
                
                # Try to go to next page
                if not self.go_to_next_page():
                    self.logger.info("No more pages available")
                    break
                
                page_num += 1
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Scraping completed!")
            self.logger.info(f"Total processed: {total_processed}")
            self.logger.info(f"Total skipped (already downloaded): {total_skipped}")
            self.logger.info(f"{'='*60}")
            
        except Exception as e:
            self.logger.error(f"Error in scrape_all_products: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function"""
    import argparse
    
    def str_to_bool(v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')
    
    parser = argparse.ArgumentParser(description='Search and scrape NYSPAD products that need PDF download')
    parser.add_argument('--headless', type=str_to_bool, default=False, nargs='?', const=True,
                       help='Run browser in headless mode (default: False, use --headless or --headless=True for True)')
    parser.add_argument('--max-products', type=int, default=None,
                       help='Maximum number of products to process (default: all products that need PDFs)')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay for individual operations in seconds (default: 2.0)')
    parser.add_argument('--csv', type=str, default='current_products_edited.csv',
                       help='Path to CSV file relative to nyspad_csv_downloads (default: current_products_edited.csv)')
    parser.add_argument('--max-workers', type=int, default=6,
                       help='Maximum number of concurrent browser instances (default: 6)')
    parser.add_argument('--start-delay', type=float, default=10.0,
                       help='Minimum seconds between starting new browsers (default: 10.0)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"NYSPAD Parallel Search Scraper")
    print(f"{'='*60}")
    print(f"Max concurrent browsers: {args.max_workers}")
    print(f"Start delay: {args.start_delay}s")
    print(f"Headless mode: {args.headless}")
    print(f"Products to process: {args.max_products if args.max_products else 'ALL'}")
    print(f"{'='*60}\n")
    
    with NewNYSPADScraper(headless=args.headless, delay=args.delay, csv_path=args.csv) as scraper:
        scraper.scrape_products_from_csv(
            max_products=args.max_products,
            max_workers=args.max_workers,
            start_delay=args.start_delay
        )


if __name__ == "__main__":
    main()

