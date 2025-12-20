#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def debug_search_type():
    """Debug script to find the correct search type values"""
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Navigate to the page
        driver.get("https://extapps.dec.ny.gov/nyspad/products")
        time.sleep(3)
        
        # Handle Notice modal
        try:
            continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
            continue_button.click()
            time.sleep(2)
        except:
            pass
        
        # Find the hidden input field
        hidden_input = driver.find_element(By.CSS_SELECTOR, "input[name='searchFormPanelContainer:searchForm:form:registrationNoType']")
        print(f"Hidden input found: {hidden_input.get_attribute('name')}")
        print(f"Current value: {hidden_input.get_attribute('value')}")
        
        # Try to find all possible values by looking at the Select2 options
        try:
            # Click the Select2 container to open dropdown
            select2_container = driver.find_element(By.CSS_SELECTOR, ".select2-container")
            select2_container.click()
            time.sleep(1)
            
            # Find all options
            options = driver.find_elements(By.CSS_SELECTOR, ".select2-results li")
            print(f"\nFound {len(options)} options:")
            for i, option in enumerate(options):
                text = option.text.strip()
                value = option.get_attribute('data-value') or option.get_attribute('value') or 'no-value'
                print(f"  {i}: '{text}' (value: {value})")
                
        except Exception as e:
            print(f"Could not get options: {e}")
        
        # Try different values
        test_values = ['EPA_REG_NO', 'EPA_REG_NUMBER', 'REGISTRATION_NO', 'REG_NO', 'EPA', 'REGISTRATION']
        
        for value in test_values:
            try:
                driver.execute_script("arguments[0].value = arguments[1];", hidden_input, value)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", hidden_input)
                print(f"\nTried value: {value}")
                print(f"New value: {hidden_input.get_attribute('value')}")
                time.sleep(1)
            except Exception as e:
                print(f"Error with value {value}: {e}")
        
        input("Press Enter to continue...")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_search_type()
