import os
import time
import shutil
import csv
import string
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

CHROME_DRIVER_PATH = r'c:\PlaceYouInstalledSelenium\chromedriver.exe'
BASE_DOWNLOAD_DIR = r'F:\PlaceToSendItToOnceConfirmed'
DEFAULT_DOWNLOAD_DIR = r'C:\DownloadDestination'
JAM_SUBMISSIONS_URL = 'https://itch.io/jam/JAMIDNUMBERHERE/entry-downloads'

USERNAME = 'YOURCREDENTIALS HERE'
PASSWORD = 'YOURCREDENTIALS HERE'

chrome_options = webdriver.ChromeOptions()
prefs = {
    "profile.default_content_settings.popups": 0,
    "download.default_directory": DEFAULT_DOWNLOAD_DIR,
    "safebrowsing.enabled": "false", 
}
chrome_options.add_experimental_option("prefs", prefs)


service = Service(CHROME_DRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)
submissions_dict = {}

def login_to_itchio():
    driver.get('https://itch.io/login')
    
    username_input = driver.find_element(By.NAME, 'username')
    password_input = driver.find_element(By.NAME, 'password')
    
    username_input.send_keys(USERNAME)
    password_input.send_keys(PASSWORD)
    
    password_input.send_keys(Keys.RETURN)
    time.sleep(3)  
    
    # Pause for CAPTCHA (if it appears)
    input("If there is a CAPTCHA, please solve it. Press Enter to continue...")


def sanitize_folder_name(name):   
    allowed_chars = string.ascii_letters + string.digits + "_"
    sanitized_name = "".join(c if c in allowed_chars else "_" for c in name)
    return sanitized_name[:150]  # Truncate to avoid path length issues

def sanitize_file_name(name):
    allowed_chars = string.ascii_letters + string.digits + "_"
    sanitized_name = "".join(c if c in allowed_chars else "" for c in name)
    return sanitized_name[:150]  # Truncate to avoid path length issues

def sanitize_xpath_string(text):  
    return text.replace('"', "'")

def wait_for_expected_files(expected_count, download_dir, timeout=600):
    start_time = time.time()
    while True:
        downloaded_files = [f for f in os.listdir(download_dir) if not f.endswith('.crdownload')]
        if len(downloaded_files) >= expected_count:
            return downloaded_files
        if time.time() - start_time > timeout:
            raise Exception(f"Timeout waiting for {expected_count} files.")
        time.sleep(5)

def gather_submission_names():
    driver.get(JAM_SUBMISSIONS_URL)
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'entry_link')))
    submission_elements = driver.find_elements(By.CLASS_NAME, 'entry_link')
    submission_names = [element.text.strip() for element in submission_elements]
    
    return submission_names


def create_expected_files(submission_name, file_names):  
    sanitized_folder_name = sanitize_folder_name(submission_name)
    submission_folder = os.path.join(BASE_DOWNLOAD_DIR, sanitized_folder_name)

    if not os.path.exists(submission_folder):
        os.makedirs(submission_folder)

    for file_name in file_names:
        try:
            sanitized_file_name = sanitize_file_name(file_name)
            expected_file_name = f"{sanitized_file_name}.expected"
            expected_file_path = os.path.join(submission_folder, expected_file_name)  
            with open(expected_file_path, 'w', encoding='utf-8') as f:
                print(f"Expected file: {file_name}")
                f.write(f"Expected file: {file_name}")

        except (OSError, UnicodeEncodeError) as e:  
            print(f"Error creating expected file for {file_name}: {e}")
            invalid_file_name = 'Invalid_Filename.Expected'
            invalid_file_path = os.path.join(submission_folder, invalid_file_name)

            with open(invalid_file_path, 'w', encoding='utf-8') as f:
                f.write(f"Invalid file: {file_name} - Error: {e}")

def gather_and_create_expected_files():
    """Gathers all entries and creates .expected files and folders for each submission."""
    submission_names = gather_submission_names()
    
    for submission_name in submission_names:
        try:
            submission_row = driver.find_element(By.XPATH, f'//a[text()="{sanitize_xpath_string(submission_name)}"]/ancestor::tr')
            download_buttons = submission_row.find_elements(By.CLASS_NAME, 'upload_download_btn')
            file_names = [btn.find_element(By.CLASS_NAME, 'name').text for btn in download_buttons]

            create_expected_files(submission_name, file_names)

            submissions_dict[submission_name] = False

        except NoSuchElementException:
            print(f"Could not find submission: {submission_name}. Skipping...")
            submissions_dict[submission_name] = False

def wait_for_new_files(before_files, download_dir, expected_count, timeout=60000):
    """Wait for new files in the download directory."""
    start_time = time.time()
    while True:
        after_files = set(os.listdir(download_dir)) - before_files  
        downloaded_files = [f for f in after_files if not f.endswith('.crdownload')]  # Ignore temp files

        if len(downloaded_files) >= expected_count:
            return downloaded_files  # Return only new files
        if time.time() - start_time > timeout:
            raise Exception(f"Timeout waiting for {expected_count} files.")
        time.sleep(5)

def download_files_for_submission(submission_name):
    """Download all files for a specific submission and handle any unexpected navigation."""
    print(f"Processing submission: {submission_name}")
    
    sanitized_submission_name = sanitize_xpath_string(submission_name)
    
    try:
        submission_row = driver.find_element(By.XPATH, f'//a[text()="{sanitized_submission_name}"]/ancestor::tr')
        download_buttons = submission_row.find_elements(By.CLASS_NAME, 'upload_download_btn')
        
        expected_files_count = len(download_buttons)
        print(f"Expecting {expected_files_count} file(s) for {submission_name}.")
        
        before_files = set(os.listdir(DEFAULT_DOWNLOAD_DIR))
        
        current_url = driver.current_url
                
        for button in download_buttons:
            button.click()
            time.sleep(2)  
            
                if driver.current_url != current_url:
                print(f"Navigation detected after clicking a download button for {submission_name}. Returning to the submissions page.")
                
                driver.get(JAM_SUBMISSIONS_URL)
                time.sleep(3)  # Wait for the page to reload
                
                # Mark this submission as complete and skip it
                submissions_dict[submission_name] = True
                print(f"Skipping submission: {submission_name} due to navigation.")
                return
        
        # Wait for the expected number of files to be downloaded
        downloaded_files = wait_for_new_files(before_files, DEFAULT_DOWNLOAD_DIR, expected_files_count)
        
        # Move downloaded files to the correct submission folder
        sanitized_folder_name = sanitize_folder_name(submission_name)
        submission_folder = os.path.join(BASE_DOWNLOAD_DIR, sanitized_folder_name)

        if not os.path.exists(submission_folder):
            os.makedirs(submission_folder)

        for file_name in downloaded_files:
            src = os.path.join(DEFAULT_DOWNLOAD_DIR, file_name)
            dest = os.path.join(submission_folder, file_name)
            shutil.move(src, dest)
            print(f"Moved {file_name} to {submission_folder}")

        # Mark the submission as processed
        submissions_dict[submission_name] = True

    except NoSuchElementException:
        print(f"Could not find submission: {submission_name}. Skipping...")
        submissions_dict[submission_name] = False

def check_and_resume():
    for submission_name in submissions_dict:
        sanitized_folder_name = sanitize_folder_name(submission_name)
        submission_folder = os.path.join(BASE_DOWNLOAD_DIR, sanitized_folder_name)       
        if os.path.exists(submission_folder):
            downloaded_files = [f for f in os.listdir(submission_folder) if not f.endswith('.expected')]
            expected_files = [f for f in os.listdir(submission_folder) if f.endswith('.expected')]

            if len(downloaded_files) == len(expected_files):
                print(f"Submission {submission_name} already processed.")
                submissions_dict[submission_name] = True
            else:
                submissions_dict[submission_name] = False  # Needs to be processed
        else:
            submissions_dict[submission_name] = False  # Needs to be processed

import csv
import os

def export_to_csv(output_filename='submission_report.csv'):
    """Export submission data to a CSV file in the BASE_DOWNLOAD_DIR."""
    output_path = os.path.join(BASE_DOWNLOAD_DIR, output_filename)  # Save to BASE_DOWNLOAD_DIR
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Submission Name', '.expected Files', 'Other Files', 'Match']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Iterate over submission directories
        for submission_name in submissions_dict.keys():
            sanitized_folder_name = sanitize_folder_name(submission_name)
            submission_folder = os.path.join(BASE_DOWNLOAD_DIR, sanitized_folder_name)

            if os.path.exists(submission_folder):
                # Count the number of .expected files and other files in the folder
                expected_files = [f for f in os.listdir(submission_folder) if f.endswith('.expected')]
                other_files = [f for f in os.listdir(submission_folder) if not f.endswith('.expected')]

                # Determine if the counts match
                files_match = len(expected_files) == len(other_files)

                # Write the row to the CSV
                writer.writerow({
                    'Submission Name': submission_name,
                    '.expected Files': len(expected_files),
                    'Other Files': len(other_files),
                    'Match': files_match
                })
    
    print(f"CSV export completed: {output_path}")

def cleanup_excess_files():
    for submission_name in submissions_dict.keys():
        sanitized_folder_name = sanitize_folder_name(submission_name)
        submission_folder = os.path.join(BASE_DOWNLOAD_DIR, sanitized_folder_name)

        if os.path.exists(submission_folder):
            # Find files with underscores that shouldn't exist and delete them
            files_in_folder = os.listdir(submission_folder)
            for file_name in files_in_folder:
                if "_.expected" in file_name:  # Look for incorrectly sanitized files???
                    file_path = os.path.join(submission_folder, file_name)
                    print(f"Cleaning up excess file: {file_name}")
                    os.remove(file_path)

def main():
    cleanup_excess_files()
    login_to_itchio()
    
    # Step 1: Gather and create expected files for all submissions
    gather_and_create_expected_files()
    
    # Step 2: Check if submissions are already processed
    check_and_resume()  # Update based on existing files
    
    # Step 3: Process each submission, skipping already processed ones
    for submission_name, is_processed in submissions_dict.items():
        if not is_processed:
            try:
                download_files_for_submission(submission_name)
            except Exception as e:
                print(f"Error processing {submission_name}: {e}")
                # Handle timeout or refresh situation, refresh page and continue
    driver.quit()
    

if __name__ == "__main__":
    main()
    export_to_csv()
      
