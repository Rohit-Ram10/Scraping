import time
import csv
import random
import sys
import os

# --- FIX FOR PYTHON 3.12+ ---
try:
    import setuptools
except ImportError:
    pass
# ----------------------------

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# --- CONFIGURATION ---
LOGIN_URL = "https://www.carlislebrass.com/customer/account/login/"
USERNAME = "accountsuk@euro-art.co.uk" 
PASSWORD = "Hasanpur1"          

def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    
    # --- MAGIC FIX: PERSISTENT PROFILE ---
    # This creates a folder named 'chrome_profile' in your script's folder.
    # It saves your login cookies so you don't have to log in every time.
    profile_path = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_path}")
    
    # Initialize driver
    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver

def random_sleep(min_s=10.0, max_s=12.0):
    time.sleep(random.uniform(min_s, max_s))

def handle_cookie_banner(driver):
    """Clicks generic cookie buttons if they appear."""
    try:
        # Try finding common cookie button IDs
        selectors = [
            (By.ID, "btn-cookie-allow"), 
            (By.ID, "onetrust-accept-btn-handler"),
            (By.CSS_SELECTOR, "button.action.allow.primary")
        ]
        for by, val in selectors:
            try:
                btn = driver.find_element(by, val)
                if btn.is_displayed():
                    btn.click()
                    print("🍪 Clicked Cookie Banner.")
                    time.sleep(1)
                    break
            except:
                continue
    except:
        pass

def login_to_site(driver):
    print("Checking login status...")
    driver.get(LOGIN_URL)
    random_sleep(10, 12)
    
    # 1. CHECK: Are we already logged in? (Thanks to Persistent Profile)
    if "/customer/account" in driver.current_url or len(driver.find_elements(By.PARTIAL_LINK_TEXT, "Sign Out")) > 0:
        print("✅ ALREADY LOGGED IN! Skipping login process.")
        return

    handle_cookie_banner(driver)

    print("Attempting to log in...")
    try:
        wait = WebDriverWait(driver, 15)
        
        # 2. Fill Email (Using JavaScript to force it if blocked)
        email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
        driver.execute_script("arguments[0].value = '';", email_field) # Clear
        driver.execute_script("arguments[0].value = arguments[1];", email_field, USERNAME)
        # Also try standard typing to trigger events
        try:
            email_field.send_keys(Keys.CONTROL, 'a') # Focus
        except:
            pass
            
        random_sleep(4, 8)
        
        # 3. Fill Password (Using JavaScript to force it)
        pass_field = driver.find_element(By.ID, "pass")
        driver.execute_script("arguments[0].value = arguments[1];", pass_field, PASSWORD)
        
        # 4. Submit
        # Try clicking the button first
        try:
            login_btn = driver.find_element(By.CSS_SELECTOR, "fieldset.login button.action.login")
            driver.execute_script("arguments[0].click();", login_btn)
        except:
            # Fallback: Hit Enter on password field
            pass_field.send_keys(Keys.RETURN)
        
        # 5. Wait for Login Success
        wait.until(EC.or_(
            EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Sign Out")),
            EC.url_contains("/customer/account")
        ))
        
        print("✅ Login Successful! Session saved.")
        random_sleep(2, 3)
        
    except Exception as e:
        print(f"⚠️ Login issue: {e}")
        # Final check if it actually worked despite error
        if "/customer/account" in driver.current_url:
            print("✅ We are on the Dashboard. Proceeding.")
        else:
            print("❌ Login failed. You may need to log in manually ONCE, then restart the script.")
            input("Press Enter to exit...")
            driver.quit()
            sys.exit()

def scrape_product(driver, url):
    print(f"Navigating to: {url}")
    driver.get(url)
    random_sleep(2, 3)
    
    product_data = []
    
    try:
        if "Forbidden" in driver.title:
            print("⚠️ Access Denied (403).")
            return []

        title = driver.find_element(By.CSS_SELECTOR, "h1.page-title span").text.strip()
    except Exception as e:
        print(f"Could not load product page: {e}")
        return []

    print(f"Scraping: {title}")

    # Check for Finish Images
    finish_images = driver.find_elements(By.CSS_SELECTOR, "#finish-images img")

    if not finish_images:
        # Simple Product
        try:
            sku = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .sku .value").text
            price = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .price").text
            product_data.append({
                "Title": title, "Finish": "N/A", "Size": "N/A", "Option": "N/A", "SKU": sku, "Price": price
            })
        except:
            pass
    else:
        # Configurable Product
        num_finishes = len(finish_images)
        for i in range(num_finishes):
            try:
                finishes = driver.find_elements(By.CSS_SELECTOR, "#finish-images img")
                if i >= len(finishes): break
                
                current_finish = finishes[i]
                finish_name = current_finish.get_attribute("title")
                
                driver.execute_script("arguments[0].click();", current_finish)
                random_sleep(2, 3) 
                
                dropdowns = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                
                if not dropdowns:
                    sku = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .sku .value").text
                    price = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .price-wrapper .price").text
                    product_data.append({
                        "Title": title, "Finish": finish_name, "Size": "N/A", "Option": "N/A", "SKU": sku, "Price": price
                    })
                else:
                    process_dropdowns(driver, dropdowns, 0, title, finish_name, [], product_data)
            except Exception as e:
                print(f"Skipping a finish: {e}")

    return product_data

def process_dropdowns(driver, dropdown_elements, index, title, finish_name, current_selections, product_data):
    if index >= len(dropdown_elements):
        try:
            sku = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .sku .value").text
            price = driver.find_element(By.CSS_SELECTOR, "div.product-info-main .price-wrapper .price").text
            size_val = current_selections[0] if len(current_selections) > 0 else "N/A"
            opt_val = current_selections[1] if len(current_selections) > 1 else "N/A"

            product_data.append({
                "Title": title, "Finish": finish_name, "Size": size_val, "Option": opt_val, "SKU": sku, "Price": price
            })
        except:
            pass
        return

    try:
        dropdowns_refreshed = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
        current_select_elem = dropdowns_refreshed[index]
        if not current_select_elem.is_enabled(): return

        select_obj = Select(current_select_elem)
        options_count = len(select_obj.options)
        
        for opt_idx in range(1, options_count):
            dropdowns_refreshed = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
            select_obj_refresh = Select(dropdowns_refreshed[index])
            
            option_text = select_obj_refresh.options[opt_idx].text.strip()
            select_obj_refresh.select_by_index(opt_idx)
            random_sleep(1.5, 2.0)
            
            new_selections = current_selections + [option_text]
            process_dropdowns(driver, dropdowns_refreshed, index + 1, title, finish_name, new_selections, product_data)
    except Exception:
        pass

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    driver = get_driver()
    
    try:
        login_to_site(driver)
        
        # URL TO SCRAPE
        test_url = "https://www.carlislebrass.com/products/accessories/turn-and-releases/disabled-thumbturn-release-42957"
        
        data = scrape_product(driver, test_url)
        print(f"\nExtracted {len(data)} items.")
        
        keys = ["Title", "Finish", "Size", "Option", "SKU", "Price"]
        with open('carlisle_data_final.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
            
    except Exception as e:
        print(f"Critical Error: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass