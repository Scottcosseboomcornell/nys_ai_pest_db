#!/usr/bin/env python3
"""
NYSPAD Integration with Existing Pipeline
Integrates NYSPAD data sources with the existing pesticide processing pipeline
"""

import os
import sys
import json
import logging
import asyncio
from typing import List, Dict, Optional, Set
import pandas as pd
from pathlib import Path

# Add the current directory to the path to import existing modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import existing pipeline modules
import sys
sys.path.append('..')  # Add parent directory to path
from APPRIL_manipulation import download_pesticide_label2
from nyspad_scraper import NYSPADScraper
from nyspad_data_parser import NYSPADDataParser

class NYSPADIntegration:
    def __init__(self, 
                 nyspad_download_dir: str = "../../pipeline_critical_docs/nyspad_pdfs",
                 data_dir: str = "../../pipeline_critical_docs/nyspad_data"):
        """
        Initialize the NYSPAD integration system
        
        Args:
            nyspad_download_dir: Directory for NYSPAD PDFs
            data_dir: Directory for NYSPAD data files
        """
        self.nyspad_download_dir = nyspad_download_dir
        self.data_dir = data_dir
        
        # Create directories
        for directory in [nyspad_download_dir, data_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('nyspad_integration.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.data_parser = NYSPADDataParser(data_dir)
        
        # Load existing pipeline data
        self.existing_registrations = self._load_existing_registrations()

    def _load_existing_registrations(self) -> Set[str]:
        """Load existing EPA registration numbers from the current pipeline"""
        existing_regs = set()
        
        try:
            # Load from APPRIL data
            csv_pattern = '../../pipeline_critical_docs/apprilDataFrame_*.csv'
            import glob
            csv_files = glob.glob(csv_pattern)
            
            if csv_files:
                csv_file_name = max(csv_files, key=os.path.getctime)
                df = pd.read_csv(csv_file_name)
                existing_regs = set(df['REG_NUM'].astype(str).tolist())
                self.logger.info(f"Loaded {len(existing_regs)} existing registrations from APPRIL data")
            
            # Also check existing PDF files
            pdf_dir = "../../pipeline_critical_docs/pdfInput"
            if os.path.exists(pdf_dir):
                pdf_files = [f.replace('.pdf', '') for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
                existing_regs.update(pdf_files)
                self.logger.info(f"Found {len(pdf_files)} existing PDF files")
            
        except Exception as e:
            self.logger.error(f"Error loading existing registrations: {e}")
        
        return existing_regs

    def find_nyspad_specific_pesticides(self) -> List[Dict]:
        """
        Find pesticides that are registered in NY but might not be in EPA data
        
        Returns:
            List of NY-specific pesticide information
        """
        ny_specific_pesticides = []
        
        try:
            # Process NYSPAD data files
            self.logger.info("Processing NYSPAD data files...")
            data_results = self.data_parser.process_all_data_files()
            
            # Extract unique registrations from NYSPAD data
            nyspad_registrations = set()
            for link_info in data_results.get('download_links', []):
                reg = link_info.get('epa_registration', '')
                if reg:
                    nyspad_registrations.add(reg)
            
            # Find registrations not in existing pipeline
            new_registrations = nyspad_registrations - self.existing_registrations
            
            self.logger.info(f"Found {len(new_registrations)} NY-specific registrations not in existing pipeline")
            
            # Get detailed information for new registrations
            for reg in new_registrations:
                try:
                    # These are NYSPAD-specific registrations
                    ny_specific_pesticides.append({
                        'registration': reg,
                        'source': 'NYSPAD_ONLY',
                        'info': {'epa_registration': reg}
                    })
                    
                except Exception as e:
                    self.logger.warning(f"Error processing registration {reg}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error finding NY-specific pesticides: {e}")
        
        return ny_specific_pesticides

    def download_missing_labels(self, registration_numbers: List[str] = None) -> Dict:
        """
        Download labels for pesticides not currently in the pipeline
        
        Args:
            registration_numbers: Specific registration numbers to download (if None, finds missing ones)
            
        Returns:
            Summary of download results
        """
        results = {
            'total_requested': 0,
            'nyspad_downloads': 0,
            'failed_downloads': 0,
            'errors': [],
            'downloaded_files': []
        }
        
        try:
            if registration_numbers is None:
                # Find missing registrations
                missing_regs = self._find_missing_registrations()
            else:
                missing_regs = registration_numbers
            
            results['total_requested'] = len(missing_regs)
            self.logger.info(f"Downloading labels for {len(missing_regs)} missing registrations")
            
            for reg in missing_regs:
                try:
                    self.logger.info(f"Processing registration: {reg}")
                    
                    # Try NYSPAD data files first
                    nyspad_success = self._download_from_nyspad_data(reg)
                    if nyspad_success:
                        results['nyspad_downloads'] += 1
                        results['downloaded_files'].append(f"{reg}.pdf")
                        continue
                    
                    # Try NYSPAD web scraper as fallback
                    scraper_success = self._download_from_nyspad_scraper(reg)
                    if scraper_success:
                        results['nyspad_downloads'] += 1
                        results['downloaded_files'].append(f"{reg}.pdf")
                        continue
                    
                    # All methods failed
                    results['failed_downloads'] += 1
                    results['errors'].append(f"Failed to download label for {reg}")
                    
                except Exception as e:
                    error_msg = f"Error processing registration {reg}: {e}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
                    results['failed_downloads'] += 1
            
        except Exception as e:
            self.logger.error(f"Error in download_missing_labels: {e}")
            results['errors'].append(str(e))
        
        return results

    def _find_missing_registrations(self) -> List[str]:
        """Find registration numbers that are missing from the current pipeline"""
        missing_regs = []
        
        try:
            # Get all NYSPAD registrations
            data_results = self.data_parser.process_all_data_files()
            nyspad_regs = set()
            
            for link_info in data_results.get('download_links', []):
                reg = link_info.get('epa_registration', '')
                if reg:
                    nyspad_regs.add(reg)
            
            # Find missing ones
            missing_regs = list(nyspad_regs - self.existing_registrations)
            
        except Exception as e:
            self.logger.error(f"Error finding missing registrations: {e}")
        
        return missing_regs


    def _download_from_nyspad_data(self, reg_number: str) -> bool:
        """Download label from NYSPAD data files"""
        try:
            # This would use the data parser to find and download the label
            # Implementation depends on the actual structure of NYSPAD data files
            return False  # Placeholder
        except Exception as e:
            self.logger.warning(f"NYSPAD data download failed for {reg_number}: {e}")
            return False

    def _download_from_nyspad_scraper(self, reg_number: str) -> bool:
        """Download label using NYSPAD web scraper"""
        try:
            with NYSPADScraper(self.nyspad_download_dir, headless=True) as scraper:
                # Search for the registration number
                results = scraper.search_pesticide(reg_number)
                
                if results:
                    # Get details and download
                    details = scraper.get_pesticide_details(results[0]['element'])
                    
                    for doc in details.get('documents', []):
                        if scraper.download_pdf(doc):
                            return True
                
            return False
        except Exception as e:
            self.logger.warning(f"NYSPAD scraper download failed for {reg_number}: {e}")
            return False

    def integrate_with_pipeline(self, 
                              process_new_labels: bool = True,
                              update_web_app: bool = False) -> Dict:
        """
        Integrate NYSPAD data with the existing pipeline
        
        Args:
            process_new_labels: Whether to process newly downloaded labels through the pipeline
            update_web_app: Whether to update the web application with new data
            
        Returns:
            Integration results summary
        """
        results = {
            'new_labels_downloaded': 0,
            'labels_processed': 0,
            'web_app_updated': False,
            'errors': []
        }
        
        try:
            # Step 1: Download missing labels
            self.logger.info("Step 1: Downloading missing labels...")
            download_results = self.download_missing_labels()
            results['new_labels_downloaded'] = download_results['nyspad_downloads']
            
            if results['new_labels_downloaded'] == 0:
                self.logger.info("No new labels to process")
                return results
            
            # Step 2: Process new labels through existing pipeline
            if process_new_labels:
                self.logger.info("Step 2: Processing new labels through pipeline...")
                processed_count = self._process_new_labels_through_pipeline()
                results['labels_processed'] = processed_count
            
            # Step 3: Update web application
            if update_web_app:
                self.logger.info("Step 3: Updating web application...")
                web_update_success = self._update_web_application()
                results['web_app_updated'] = web_update_success
            
        except Exception as e:
            error_msg = f"Error in integration: {e}"
            results['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return results

    def _process_new_labels_through_pipeline(self) -> int:
        """Process newly downloaded labels through the existing pipeline"""
        processed_count = 0
        
        try:
            # This would integrate with the existing pipeline scripts
            # For now, this is a placeholder that would call the appropriate functions
            
            # Import and use existing pipeline functions
            from fitzandcamelot import parse_text_single
            from ai_main_o4_chat import ai_part_o4_chat_async
            from post_extraction_alter_json import process_single_label
            
            # Get list of new PDF files
            pdf_dir = "../../pipeline_critical_docs/pdfInput"
            new_pdfs = []
            
            for filename in os.listdir(pdf_dir):
                if filename.endswith('.pdf'):
                    reg_number = filename.replace('.pdf', '')
                    if reg_number not in self.existing_registrations:
                        new_pdfs.append(reg_number)
            
            self.logger.info(f"Processing {len(new_pdfs)} new labels through pipeline")
            
            # Process each new label
            for reg_number in new_pdfs:
                try:
                    # Parse text
                    parse_text_single(reg_number)
                    
                    # AI extraction (this would need to be adapted for async processing)
                    # ai_part_o4_chat_async(reg_number, ...)
                    
                    # Post-extraction processing
                    # process_single_label(reg_number)
                    
                    processed_count += 1
                    self.logger.info(f"Processed label: {reg_number}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing label {reg_number}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error in _process_new_labels_through_pipeline: {e}")
        
        return processed_count

    def _update_web_application(self) -> bool:
        """Update the web application with new data"""
        try:
            # This would run the web application update scripts
            import subprocess
            
            # Change to web application directory
            web_app_dir = "../../web_application"
            original_dir = os.getcwd()
            
            try:
                os.chdir(web_app_dir)
                
                # Run the update scripts
                subprocess.run(["./prepare_altered_json.sh"], check=True)
                subprocess.run(["./deploy_complete_update.sh"], check=True)
                
                return True
                
            finally:
                os.chdir(original_dir)
                
        except Exception as e:
            self.logger.error(f"Error updating web application: {e}")
            return False

    def generate_integration_report(self, results: Dict) -> str:
        """Generate a comprehensive integration report"""
        report = f"""
NYSPAD Integration Report
========================

Summary:
- New labels downloaded: {results.get('new_labels_downloaded', 0)}
- Labels processed through pipeline: {results.get('labels_processed', 0)}
- Web application updated: {'Yes' if results.get('web_app_updated', False) else 'No'}

Errors ({len(results.get('errors', []))}):
"""
        
        for error in results.get('errors', []):
            report += f"- {error}\n"
        
        return report

    def save_integration_results(self, results: Dict, filename: str = "nyspad_integration_results.json"):
        """Save integration results to JSON file"""
        try:
            filepath = os.path.join(self.data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            self.logger.info(f"Integration results saved to: {filepath}")
        except Exception as e:
            self.logger.error(f"Error saving integration results: {e}")


def main():
    """Main function to run the integration"""
    integration = NYSPADIntegration()
    
    # Run the integration
    results = integration.integrate_with_pipeline(
        process_new_labels=True,
        update_web_app=False  # Set to True when ready to update web app
    )
    
    # Generate and print report
    report = integration.generate_integration_report(results)
    print(report)
    
    # Save results
    integration.save_integration_results(results)


if __name__ == "__main__":
    main()
