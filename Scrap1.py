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
# Use the product you are testing
PRODUCT_URL = "https://www.carlislebrass.com/products/accessories/escutcheons/standard-profile-escutcheon-51003"
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
        print(f"Login skipped (might be already logged in): {e}")

def wait_for_loading_mask():
    """Waits for the Magento spinner to appear and then disappear."""
    try:
        # Wait for mask to be invisible
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "loading-mask")))
    except:
        pass
    time.sleep(4) # Safety buffer

def get_dropdown_label(select_element):
    """Finds the label text associated with a select element (e.g. 'Size', 'Option')"""
    try:
        # Magento structure: <div class="field"><label><span>TEXT</span></label>...<select>
        label_elem = select_element.find_element(By.XPATH, "./ancestor::div[contains(@class,'field')]/label/span")
        return label_elem.text.lower()
    except:
        return "unknown"

def scrape_product_combinations():
    print(f"Navigating to product: {PRODUCT_URL}")
    driver.get(PRODUCT_URL)
    wait_for_loading_mask()

    # 1. FIND FINISHES
    try:
        finish_container = driver.find_element(By.ID, "finish-images")
        finish_images = finish_container.find_elements(By.TAG_NAME, "img")
    except:
        finish_images = []

    if not finish_images:
        finish_images = [None] # Dummy list for loop

    # --- LOOP 1: FINISHES ---
    for f_index in range(len(finish_images)):
        finish_name = "Default"
        
        # Click Finish Image
        if finish_images[0] is not None:
            try:
                # Re-find element
                finish_container = driver.find_element(By.ID, "finish-images")
                current_img = finish_container.find_elements(By.TAG_NAME, "img")[f_index]
                finish_name = current_img.get_attribute("title")
                
                print(f"\n--- Finish: {finish_name} ---")
                
                # Scroll & Click
                driver.execute_script("arguments[0].scrollIntoView(true);", current_img)
                driver.execute_script("arguments[0].click();", current_img)
                
                wait_for_loading_mask()
            except Exception as e:
                print(f"Error selecting finish: {e}")
                continue

        # 2. FIND DROPDOWNS
        # We re-find them here because clicking the finish might have changed them
        dropdowns = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
        
        if not dropdowns:
            # No dropdowns, just scrape the finish
            scrape_details(finish_name, "N/A", "N/A")
            continue

        # --- LOOP 2: FIRST DROPDOWN ---
        # Identify what this dropdown is (Size or Option?)
        select_1_elem = dropdowns[0]
        label_1 = get_dropdown_label(select_1_elem)
        
        s1 = Select(select_1_elem)
        count_1 = len(s1.options)

        for i in range(count_1):
            # Refresh DOM
            dropdowns = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
            s1 = Select(dropdowns[0])
            
            # Skip "Choose an option"
            val_1_code = s1.options[i].get_attribute("value")
            if not val_1_code: continue

            # Select Option 1
            # We use select_by_index, but we rely on Magento to have filtered this list
            # based on the finish click earlier.
            try:
                s1.select_by_index(i)
            except:
                continue # If selection fails, skip

            val_1_text = s1.options[i].text.strip()
            wait_for_loading_mask()

            # Assign to correct column variable
            size_val = "N/A"
            option_val = "N/A"

            if "size" in label_1 or "length" in label_1:
                size_val = val_1_text
            else:
                option_val = val_1_text

            # --- LOOP 3: SECOND DROPDOWN (If it exists) ---
            dropdowns_level_2 = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
            
            if len(dropdowns_level_2) > 1:
                select_2_elem = dropdowns_level_2[1]
                label_2 = get_dropdown_label(select_2_elem)
                
                s2 = Select(select_2_elem)
                count_2 = len(s2.options)

                for j in range(count_2):
                    # Refresh DOM
                    dropdowns_level_3 = driver.find_elements(By.CSS_SELECTOR, "select.super-attribute-select")
                    s2_refresh = Select(dropdowns_level_3[1])

                    val_2_code = s2_refresh.options[j].get_attribute("value")
                    if not val_2_code: continue

                    try:
                        s2_refresh.select_by_index(j)
                    except:
                        continue

                    val_2_text = s2_refresh.options[j].text.strip()
                    wait_for_loading_mask()

                    # Map 2nd dropdown to variable
                    if "size" in label_2 or "length" in label_2:
                        size_val = val_2_text
                    else:
                        option_val = val_2_text # Likely "Boxed", "Standard", etc.

                    scrape_details(finish_name, size_val, option_val)
            else:
                # No second dropdown
                scrape_details(finish_name, size_val, option_val)

def scrape_details(finish, size, option):
    # Get SKU
    try:
        sku = driver.find_element(By.CSS_SELECTOR, "div.product.attribute.sku .value").text
    except:
        sku = "Error"
    
    # Get Price
    try:
        # Tries to find the final price (handling special price / normal price structure)
        price_box = driver.find_element(By.CSS_SELECTOR, ".price-box .price")
        price = price_box.text
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