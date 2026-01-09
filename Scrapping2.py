import time
import csv
import os
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
LOGIN_URL = "https://www.carlislebrass.com/customer/account/login/"
USERNAME = "accountsuk@euro-art.co.uk"
PASSWORD = "Hasanpur1"
OUTPUT_FILE = 'carlisle_data_correct.csv'

def get_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    
    # Bypass 403 block using standard automation flags removal
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def wait_for_loading_mask(driver):
    """Waits for the spinning loader to appear and then disappear."""
    try:
        # Wait briefly for mask to appear
        WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "loading-mask")))
        # Wait for it to disappear (max 10s)
        WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.CLASS_NAME, "loading-mask")))
    except:
        pass # If mask didn't appear, continue

def save_row(row_dict):
    """Saves data to CSV immediately."""
    file_exists = os.path.isfile(OUTPUT_FILE)
    fieldnames = ["Title", "Finish", "Size", "Option", "SKU", "Price"]
    
    with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)

def get_dropdown_type(dropdown_element):
    """
    Checks the label above the dropdown to see if it is 'Size' or 'Option'.
    Returns: 'Size', 'Option', or 'Unknown'
    """
    try:
        # Navigate up to the container div
        parent = dropdown_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'field')]")
        # Find the label text
        label_text = parent.find_element(By.CSS_SELECTOR, "label.label span").text.strip().lower()
        
        if "size" in label_text:
            return "Size"
        elif "option" in label_text or "locking" in label_text:
            return "Option"
        return "Unknown"
    except:
        return "Unknown"

def login_to_site(driver):
    print("Checking login status...")
    driver.get(LOGIN_URL)
    time.sleep(15)
    
    if "/customer/account" in driver.current_url or len(driver.find_elements(By.PARTIAL_LINK_TEXT, "Sign Out")) > 0:
        print("✅ Already Logged In")
        return

    print("Logging in...")
    try:
        wait = WebDriverWait(driver, 15)
        email = wait.until(EC.element_to_be_clickable((By.ID, "email")))
        email.clear(); email.send_keys(USERNAME)
        
        pwd = driver.find_element(By.ID, "pass")
        pwd.clear(); pwd.send_keys(PASSWORD)
        pwd.send_keys(Keys.RETURN)
        
        wait.until(EC.url_contains("/customer/account"))
        print("✅ Login Successful")
    except Exception as e:
        print(f"Login Warning: {e}")

def scrape_product(driver, url):
    print(f"\nNavigating to: {url}")
    driver.get(url)
    wait_for_loading_mask(driver)
    
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1.page-title span").text.strip()
    except:
        print("Could not find product title.")
        return

    print(f"Product: {title}")

    # 1. Get Finish Names
    finish_imgs = driver.find_elements(By.CSS_SELECTOR, "#finish-images img")
    finish_names = [img.get_attribute("title") for img in finish_imgs]
    
    if not finish_names:
        # Simple Product (No variations)
        try:
            sku = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .sku .value").text
            price = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .price-wrapper .price").text
            save_row({"Title": title, "Finish": "N/A", "Size": "N/A", "Option": "N/A", "SKU": sku, "Price": price})
        except:
            print("Failed to scrape simple product.")
        return

    print(f"Found Finishes: {finish_names}")

    # --- LOOP FINISHES ---
    for finish in finish_names:
        try:
            print(f"--- Processing: {finish} ---")
            
            # REFRESH to reset state
            driver.get(url)
            wait_for_loading_mask(driver)
            
            # Click Finish
            img = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//div[@id='finish-images']//img[@title='{finish}']"))
            )
            driver.execute_script("arguments[0].click();", img)
            wait_for_loading_mask(driver)
            time.sleep(1) # Let DOM settle
            
            # Find Dropdowns
            all_selects = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
            
            # Map Dropdowns (Identify which is Size, which is Option)
            size_select_element = None
            option_select_element = None
            
            for sel in all_selects:
                if sel.is_displayed():
                    dtype = get_dropdown_type(sel)
                    if dtype == "Size": size_select_element = sel
                    elif dtype == "Option": option_select_element = sel
            
            # --- SCENARIO 1: HAS SIZE ---
            if size_select_element:
                # Get all Size options text (Skip "Choose...")
                s_obj = Select(size_select_element)
                size_opts = [o.text.strip() for o in s_obj.options if o.text.strip() != "" and "Choose" not in o.text]
                
                for size_text in size_opts:
                    # RE-FIND Size Element (avoid stale element)
                    # We have to look through all selects again to find the visible "Size" one
                    re_selects = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                    target_size_elem = None
                    for rs in re_selects:
                        if rs.is_displayed() and get_dropdown_type(rs) == "Size":
                            target_size_elem = rs
                            break
                    
                    # Select Size
                    if target_size_elem:
                        Select(target_size_elem).select_by_visible_text(size_text)
                        wait_for_loading_mask(driver)
                        time.sleep(0.5)
                    
                    # --- CHECK FOR OPTIONS (Nested) ---
                    # Now that Size is selected, Option dropdown might have updated or appeared
                    re_selects = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                    target_opt_elem = None
                    for rs in re_selects:
                        if rs.is_displayed() and get_dropdown_type(rs) == "Option":
                            target_opt_elem = rs
                            break
                    
                    if target_opt_elem:
                        # Iterate Options
                        o_obj = Select(target_opt_elem)
                        opt_opts = [o.text.strip() for o in o_obj.options if o.text.strip() != "" and "Choose" not in o.text]
                        
                        for opt_text in opt_opts:
                            # Re-Find Option Element
                            final_selects = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                            final_opt_elem = None
                            for fs in final_selects:
                                if fs.is_displayed() and get_dropdown_type(fs) == "Option":
                                    final_opt_elem = fs
                                    break
                            
                            if final_opt_elem:
                                Select(final_opt_elem).select_by_visible_text(opt_text)
                                wait_for_loading_mask(driver)
                                time.sleep(0.5)
                                
                                # SCRAPE
                                scrape_data(driver, title, finish, size_text, opt_text)
                    else:
                        # Scrape (Size selected, No Option available)
                        scrape_data(driver, title, finish, size_text, "N/A")

            # --- SCENARIO 2: NO SIZE, ONLY OPTIONS (Rare) ---
            elif option_select_element and not size_select_element:
                o_obj = Select(option_select_element)
                opt_opts = [o.text.strip() for o in o_obj.options if o.text.strip() != "" and "Choose" not in o.text]
                
                for opt_text in opt_opts:
                    # Re-find
                    re_selects = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                    target_opt_elem = None
                    for rs in re_selects:
                        if rs.is_displayed() and get_dropdown_type(rs) == "Option":
                            target_opt_elem = rs
                            break
                    
                    if target_opt_elem:
                        Select(target_opt_elem).select_by_visible_text(opt_text)
                        wait_for_loading_mask(driver)
                        
                        scrape_data(driver, title, finish, "N/A", opt_text)

            # --- SCENARIO 3: DIRECT PRODUCT (Finish selected, no dropdowns) ---
            else:
                scrape_data(driver, title, finish, "N/A", "N/A")

        except Exception as e:
            print(f"⚠️ Error on finish '{finish}': {e}")

def scrape_data(driver, title, finish, size, option):
    try:
        # Be precise with Price Wrapper to avoid getting £0.00 hidden prices
        sku = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .sku .value").text
        price = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .price-wrapper .price").text
        
        print(f"   Saved: {finish} | {size} | {option} | {sku} | {price}")
        
        save_row({
            "Title": title,
            "Finish": finish,
            "Size": size,
            "Option": option,
            "SKU": sku,
            "Price": price
        })
    except Exception as e:
        print(f"   Error extracting data: {e}")

# --- MAIN ---
if __name__ == "__main__":
    driver = get_driver()
    try:
        login_to_site(driver)
        
        url = "https://www.carlislebrass.com/products/window-fittings/casement-stays/victorian-casement-stay-range"
        scrape_product(driver, url)
        
        print(f"\nDone. Saved to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Critical Error: {e}")
    finally:
        driver.quit()