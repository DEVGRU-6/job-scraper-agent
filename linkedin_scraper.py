import os
import json
import time
import requests
import gspread
from langdetect import detect, LangDetectException

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀"
DISCOVERY_TAB = "Discovered Jobs (API)"

# The exact search terms you want to query on LinkedIn
SEARCH_TERMS = ["Aviation Graduate", "Logistics Trainee", "Supply Chain Graduate"]

# Expanded locations: Fantastic.jobs supports all of these globally!
TARGET_LOCATIONS = [
    "Germany", "United Kingdom", "Singapore", "Australia", 
    "United Arab Emirates", "Qatar", "Japan", "Thailand", 
    "Hong Kong", "China"
]

# 🛑 THE BLACKLIST: Keeps the junk out
EXCLUDED_TERMS = [
    "trade", "construction", "labour", "labor", "warehouse", 
    "driver", "operator", "technician", "mechanic", "picker", 
    "packer", "forklift", "plumber", "electrician", "retail",
    "senior", "machinist", "cnc", "repair", "tool maker", "toolmaker", "manager"
]

def get_spreadsheet():
    print(f"Connecting to Google Cloud to access '{GOOGLE_SHEET_NAME}'...")
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME)

def apply_sleek_formatting(sheet):
    try:
        sheet.freeze(rows=1)
        sheet.format('A1:G1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.22},
            "horizontalAlignment": "CENTER",
            "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "fontSize": 11, "bold": True}
        })
    except Exception:
        pass

def fetch_linkedin_jobs(term, location):
    """Fetches jobs using the Fantastic.jobs RapidAPI wrapper."""
    api_key = os.environ.get("RAPIDAPI_KEY")
    api_host = os.environ.get("RAPIDAPI_HOST")
    
    if not api_key or not api_host:
        print("ERROR: RapidAPI credentials missing!")
        return []

    # The Fantastic.jobs endpoint is usually the root path "/"
    url = f"https://{api_host}/"
    
    # Calculate yesterday's date in YYYY-MM-DD format to only get fresh jobs
    yesterday_stamp = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))
    
    # Custom parameters specific to the Fantastic.jobs API syntax
    querystring = {
        "title_filter": term,
        "location_filter": location,
        "date_filter": yesterday_stamp 
    }

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host
    }

    print(f"  -> Searching LinkedIn via API: '{term}' in '{location}'...")
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Handle list or nested dict safely depending on exact endpoint return
            return data.get("data", data) if isinstance(data, dict) else data
        else:
            print(f"  -> API Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"  -> Request failed: {e}")
        return []

def main():
    doc = get_spreadsheet()
    today_stamp = time.strftime("%Y-%m-%d")
    
    try:
        discovery_sheet = doc.worksheet(DISCOVERY_TAB)
    except gspread.exceptions.WorksheetNotFound:
        discovery_sheet = doc.add_worksheet(title=DISCOVERY_TAB, rows="1000", cols="7")
        
    if not discovery_sheet.get_all_values():
        discovery_sheet.append_row(["Job Title", "Company", "Location", "Category", "Status", "Link", "Date Discovered"])

    apply_sleek_formatting(discovery_sheet)
    existing_links = set(discovery_sheet.col_values(6)) 
    
    rows_to_append = []
    total_added = 0
    total_blocked = 0
    language_blocked = 0

    for location in TARGET_LOCATIONS:
        print(f"\n--- Searching Location: {location.upper()} ---")
        for term in SEARCH_TERMS:
            jobs = fetch_linkedin_jobs(term, location)
            
            for job in jobs:
                # Catch various URL keys (url, job_url, external_apply_url)
                job_url = job.get("url", job.get("job_url", job.get("external_apply_url", "")))
                
                if job_url and job_url not in existing_links:
                    title = job.get("title", "N/A")
                    # Fantastic.jobs often provides 'text' for description
                    description = job.get("description", job.get("text", "")) 
                    
                    # Company name logic safely handles string or nested dictionary
                    comp_data = job.get("company", "Unknown")
                    company = comp_data.get("name", "Unknown") if isinstance(comp_data, dict) else comp_data
                    
                    job_location = job.get("location", "Unknown")
                    
                    # 1. Blacklist Word Check
                    title_lower = title.lower()
                    if any(bad_word in title_lower for bad_word in EXCLUDED_TERMS):
                        total_blocked += 1
                        continue 
                    
                    # 2. English Language Check
                    text_to_check = f"{title} {description}"
                    try:
                        if detect(text_to_check) != 'en':
                            language_blocked += 1
                            continue
                    except LangDetectException:
                        language_blocked += 1
                        continue
                    
                    # Pass filters -> Add to sheet
                    rows_to_append.append([
                        title,
                        company,
                        job_location,
                        "LinkedIn API", 
                        "Not applied yet",
                        job_url,
                        today_stamp
                    ])
                    existing_links.add(job_url)
                    total_added += 1

            # Pause for 2 seconds to avoid hitting RapidAPI's requests-per-second limit
            time.sleep(2)

    if rows_to_append:
        print(f"\nPushing {total_added} new LinkedIn jobs to the Google Sheet...")
        discovery_sheet.append_rows(rows_to_append)
    else:
        print("\nNo new unique LinkedIn jobs found today.")
        
    print(f"Done! Added {total_added} leads. Blocked {total_blocked} irrelevant jobs and {language_blocked} non-English jobs.")

if __name__ == "__main__":
    main()
