import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
LOGIN_URL = "https://www.carlislebrass.com/customer/account/login/"
PRODUCT_URL = "https://www.carlislebrass.com/products/window-fittings/casement-stays/bulb-end-casement-stay-50404"
USERNAME = "accountsuk@euro-art.co.uk"
PASSWORD = "Hasanpur1"

# Setup Chrome
options = webdriver.ChromeOptions()
# options.add_argument("--headless") 
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

def login():
    print("Logging in...")
    driver.get(LOGIN_URL)
    try:
        driver.find_element(By.ID, "email").send_keys(USERNAME)
        driver.find_element(By.ID, "pass").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button.action.login.primary").click()
        time.sleep(4) 
    except Exception as e:
        print(f"Login skipped or failed: {e}")

def wait_for_loading_mask():
    """Waits for the Magento loading spinner to disappear"""
    try:
        # Magento usually has a div with class 'loading-mask'
        # We wait until it is invisible
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "loading-mask")))
    except:
        pass
    time.sleep(0.5) # Small buffer

def force_select_option(select_element, index):
    """
    Uses JavaScript to select an option by index.
    This bypasses 'ElementNotInteractableException' and works on hidden selects.
    """
    driver.execute_script("""
        var select = arguments[0];
        var index = arguments[1];
        select.selectedIndex = index;
        select.dispatchEvent(new Event('change')); 
    """, select_element, index)

def get_current_sku():
    try:
        return driver.find_element(By.CSS_SELECTOR, "div.product.attribute.sku .value").text.strip()
    except:
        return ""

def wait_for_sku_change(old_sku):
    """Waits up to 3 seconds for SKU to change"""
    try:
        WebDriverWait(driver, 3).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "div.product.attribute.sku .value").text.strip() != old_sku
        )
    except:
        pass

def scrape_product_combinations():
    print(f"Navigating to product: {PRODUCT_URL}")
    driver.get(PRODUCT_URL)
    time.sleep(3)

    # 1. FIND FINISHES
    try:
        finish_container = driver.find_element(By.ID, "finish-images")
        finish_images = finish_container.find_elements(By.TAG_NAME, "img")
    except:
        finish_images = []

    if not finish_images:
        finish_images = [None]

    # --- LOOP 1: FINISHES ---
    for f_index in range(len(finish_images)):
        finish_name = "Default"
        
        # Click Finish Image
        if finish_images[0] is not None:
            try:
                # Re-find to avoid stale element
                finish_container = driver.find_element(By.ID, "finish-images")
                current_img = finish_container.find_elements(By.TAG_NAME, "img")[f_index]
                finish_name = current_img.get_attribute("title")
                
                print(f"\n--- Processing Finish: {finish_name} ---")
                
                # Scroll to image and click
                driver.execute_script("arguments[0].scrollIntoView(true);", current_img)
                driver.execute_script("arguments[0].click();", current_img)
                
                wait_for_loading_mask()
                time.sleep(1) 
            except Exception as e:
                print(f"Skipping finish index {f_index}: {e}")
                continue

        # 2. FIND DROPDOWNS
        # We assume Dropdown 0 is "Size/Length" and Dropdown 1 is "Option/Boxed"
        dropdowns = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
        
        if not dropdowns:
            scrape_details(finish_name, "N/A", "N/A")
            continue

        # --- LOOP 2: FIRST DROPDOWN (Length/Size) ---
        first_dropdown_elem = dropdowns[0]
        first_select = Select(first_dropdown_elem)
        options_count_1 = len(first_select.options)

        for i in range(options_count_1):
            # Refresh Element References
            dropdowns = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
            s1 = Select(dropdowns[0])
            
            # Check if option is valid (has value)
            val_1 = s1.options[i].get_attribute("value")
            if not val_1: continue 

            # Force Select via JS (Solves NotInteractable error)
            old_sku = get_current_sku()
            force_select_option(dropdowns[0], i)
            wait_for_loading_mask() # Wait for spin
            
            # Get text for report
            val_1_text = s1.options[i].text.strip()
            
            # --- LOOP 3: SECOND DROPDOWN (If exists, e.g. Boxed/Polybag) ---
            dropdowns_level_2 = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
            
            if len(dropdowns_level_2) > 1:
                s2 = Select(dropdowns_level_2[1])
                options_count_2 = len(s2.options)

                for j in range(options_count_2):
                    # Refresh References
                    dropdowns_level_3 = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                    s2_refresh = Select(dropdowns_level_3[1])

                    val_2 = s2_refresh.options[j].get_attribute("value")
                    if not val_2: continue

                    old_sku_2 = get_current_sku()
                    
                    # Force Select Second Dropdown
                    force_select_option(dropdowns_level_3[1], j)
                    wait_for_loading_mask()
                    
                    # Wait for SKU to specifically change from what it was
                    wait_for_sku_change(old_sku_2)

                    val_2_text = s2_refresh.options[j].text.strip()
                    
                    scrape_details(finish_name, val_1_text, val_2_text)
            else:
                # No second dropdown, just scrape
                wait_for_sku_change(old_sku)
                scrape_details(finish_name, val_1_text, "N/A")

def scrape_details(finish, size, option):
    try:
        sku = driver.find_element(By.CSS_SELECTOR, "div.product.attribute.sku .value").text
    except:
        sku = "Error"
    
    try:
        price = driver.find_element(By.CSS_SELECTOR, ".price-box .price").text
    except:
        price = "Error"

    print(f"DATA | Finish: {finish} | Size: {size} | Option: {option} | SKU: {sku} | Price: {price}")

# --- EXECUTION ---
if __name__ == "__main__":
    try:
        login()
        scrape_product_combinations()
    finally:
        print("Closing browser...")
        driver.quit()