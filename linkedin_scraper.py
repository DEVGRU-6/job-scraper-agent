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

# Locations to search (LinkedIn is very specific, use city or country names)
TARGET_LOCATIONS = [
    "Germany", "United Kingdom", "Singapore", "Australia", 
    "United Arab Emirates", "Qatar", "Japan", "Thailand", 
    "Hong Kong", "China", "Europen Union"
]

# 🛑 THE BLACKLIST: Keeps the junk out
EXCLUDED_TERMS = [
    "trade", "construction", "labour", "labor", "warehouse", 
    "driver", "operator", "technician", "mechanic", "picker", 
    "packer", "forklift", "plumber", "electrician", "retail",
    "senior", "machinist", "cnc", "HR", "fitter", "repair", "tool maker", "toolmaker", "manager"
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
    """Fetches jobs using the RapidAPI wrapper."""
    api_key = os.environ.get("RAPIDAPI_KEY")
    api_host = os.environ.get("RAPIDAPI_HOST")
    
    if not api_key or not api_host:
        print("ERROR: RapidAPI credentials missing!")
        return []

    # Replace the URL below with the one provided in your RapidAPI dashboard if different.
    url = f"https://{api_host}/search"
    
    querystring = {
        "query": f"{term} {location}",
        "time_posted": "past_24_hours", # Only get fresh jobs!
    }

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host
    }

    print(f"  -> Searching LinkedIn via API: '{term}' in '{location}'...")
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        if response.status_code == 200:
            # Adjust '.get("data", [])' based on your specific API's JSON response
            return response.json().get("data", []) 
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
                # Adjust these keys based on what your specific RapidAPI returns
                job_url = job.get("job_url", job.get("url", ""))
                
                if job_url and job_url not in existing_links:
                    title = job.get("title", "N/A")
                    description = job.get("description", "") # Extract description for language check
                    company = job.get("company", {}).get("name", job.get("company_name", "Unknown"))
                    job_location = job.get("location", "Unknown")
                    
                    # 1. Blacklist Word Check
                    title_lower = title.lower()
                    if any(bad_word in title_lower for bad_word in EXCLUDED_TERMS):
                        total_blocked += 1
                        continue 
                    
                    # 2. English Language Check
                    text_to_check = f"{title} {description}"
                    try:
                        # If the language detected is NOT english ('en'), block it
                        if detect(text_to_check) != 'en':
                            language_blocked += 1
                            continue
                    except LangDetectException:
                        # If the detector crashes (usually due to a blank description), skip it
                        language_blocked += 1
                        continue
                    
                    # If it passes all filters, add it to the list!
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

            # Pause briefly to avoid hitting the API rate limit
            time.sleep(1.5)

    if rows_to_append:
        print(f"\nPushing {total_added} new LinkedIn jobs to the Google Sheet...")
        discovery_sheet.append_rows(rows_to_append)
    else:
        print("\nNo new unique LinkedIn jobs found today.")
        
    print(f"Done! Added {total_added} leads. Blocked {total_blocked} irrelevant jobs and {language_blocked} non-English jobs.")

if __name__ == "__main__":
    main()
