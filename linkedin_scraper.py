import os
import json
import time
import requests
import gspread
from langdetect import detect, LangDetectException

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀"
DISCOVERY_TAB = "Discovered Jobs (API)"

# The exact, official RapidAPI endpoint for JSearch
RAPIDAPI_ENDPOINT_URL = "https://jsearch.p.rapidapi.com/search"

# The Boolean Hack: Combines terms to save massive API credits
SEARCH_TERM = "Aviation Graduate OR Logistics Trainee OR Supply Chain Graduate"

# All 10 global locations!
TARGET_LOCATIONS = [
    "Germany", "United Kingdom", "Singapore", "Australia", 
    "United Arab Emirates", "Qatar", "Japan", "Thailand", 
    "Hong Kong", "China"
]

# 🛑 THE BLACKLIST
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

def fetch_jsearch_jobs(term, location):
    """Fetches jobs using the powerful JSearch Google Jobs wrapper."""
    api_key = os.environ.get("RAPIDAPI_KEY")
    api_host = os.environ.get("RAPIDAPI_HOST")
    
    if not api_key or not api_host:
        print("ERROR: RapidAPI credentials missing!")
        return []

    # JSearch specific query formatting
    querystring = {
        "query": f"{term} in {location}",
        "page": "1",
        "num_pages": "1",
        "date_posted": "week" # Grabs everything from the last 7 days!
    }

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host
    }

    print(f"  -> Searching Global Web via JSearch: '{term}' in '{location}'...")
    try:
        # 👇 CHANGED TIMEOUT TO 45 SECONDS HERE 👇
        response = requests.get(RAPIDAPI_ENDPOINT_URL, headers=headers, params=querystring, timeout=45)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", []) 
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
        jobs = fetch_jsearch_jobs(SEARCH_TERM, location)
        
        if not isinstance(jobs, list):
            continue

        for job in jobs:
            # JSearch provides direct application links, or a Google link as a backup
            job_url = job.get("job_apply_link") or job.get("job_google_link", "")
            
            if job_url and job_url not in existing_links:
                
                # Map JSearch specific JSON fields
                title = job.get("job_title", "N/A")
                description = job.get("job_description", "") 
                company = job.get("employer_name", "Unknown")
                
                # Safely format City and Country
                city = job.get("job_city", "")
                country = job.get("job_country", "")
                job_location = f"{city}, {country}".strip(", ") if city or country else "Unknown"

                # 1. BLACKLIST WORD CHECK
                title_lower = title.lower()
                if any(bad_word in title_lower for bad_word in EXCLUDED_TERMS):
                    total_blocked += 1
                    continue 
                
                # 2. ENGLISH LANGUAGE CHECK
                text_to_check = f"{title} {description}"
                try:
                    if detect(text_to_check) != 'en':
                        language_blocked += 1
                        continue
                except LangDetectException:
                    language_blocked += 1
                    continue
                
                rows_to_append.append([
                    title,
                    company,
                    job_location,
                    "JSearch API", # Tagging so you know where it came from
                    "Not applied yet",
                    job_url,
                    today_stamp
                ])
                existing_links.add(job_url)
                total_added += 1

        # Pause for 1.5 seconds to respect RapidAPI rate limits
        time.sleep(1.5)

    if rows_to_append:
        print(f"\nPushing {total_added} new Global jobs to the Google Sheet...")
        discovery_sheet.append_rows(rows_to_append)
    else:
        print("\nNo new unique Global jobs found today.")
        
    print(f"Done! Added {total_added} leads.")
    print(f"Blocked: {total_blocked} irrelevant | {language_blocked} non-English.")

if __name__ == "__main__":
    main()
