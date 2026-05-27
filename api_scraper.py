import os
import json
import time
import requests
import gspread
from langdetect import detect, LangDetectException

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀"
DISCOVERY_TAB = "Discovered Jobs (API)"

SEARCH_TERMS = ["Aviation Graduate", "Logistics Trainee", "Supply Chain Graduate", "Aerospace Internship"]
TARGET_COUNTRIES = ["gb", "de", "nl", "be", "fr", "es", "it", "at", "ch", "pl", "au", "sg"] 

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

def fetch_jobs_from_adzuna(country, search_term):
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key: return []

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id, "app_key": app_key,
        "results_per_page": 50, "what": search_term,
        "content-type": "application/json"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("results", [])
    except Exception:
        pass
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
    language_blocked = 0 # Track how many foreign language jobs we blocked!

    for country in TARGET_COUNTRIES:
        print(f"\n--- Searching Country: {country.upper()} ---")
        for term in SEARCH_TERMS:
            jobs = fetch_jobs_from_adzuna(country, term)
            
            for job in jobs:
                job_url = job.get("redirect_url", "")
                
                if job_url and job_url not in existing_links:
                    title = job.get("title", "N/A").replace("<strong>", "").replace("</strong>", "")
                    description = job.get("description", "")
                    company = job.get("company", {}).get("display_name", "Unknown")
                    location = job.get("location", {}).get("display_name", "Unknown")
                    category = job.get("category", {}).get("label", "N/A")
                    
                    # 1. Check Blacklist Words
                    if any(bad_word in title.lower() for bad_word in EXCLUDED_TERMS) or \
                       any(bad_word in category.lower() for bad_word in EXCLUDED_TERMS):
                        total_blocked += 1
                        continue 
                        
                    # 2. Check Language (Must be English)
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
                    
                    rows_to_append.append([
                        title, company, location, category,
                        "Not applied yet", job_url, today_stamp
                    ])
                    existing_links.add(job_url)
                    total_added += 1

    if rows_to_append:
        print(f"\nPushing {total_added} new English jobs to the bottom of the Google Sheet...")
        discovery_sheet.append_rows(rows_to_append)
    else:
        print("\nNo new unique jobs found today.")
        
    print(f"Done! Added {total_added} leads. Blocked {total_blocked} irrelevant jobs and {language_blocked} non-English jobs.")

if __name__ == "__main__":
    main()
