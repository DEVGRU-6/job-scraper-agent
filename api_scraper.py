import os
import json
import time
import requests
import gspread

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀"
DISCOVERY_TAB = "Discovered Jobs (API)"

# The job keywords you want to mass-search
SEARCH_TERMS = ["Aviation Graduate", "Logistics Trainee", "Supply Chain Graduate", "Aerospace Internship"]

# Adzuna Country Codes (gb=UK, de=Germany, fr=France, nl=Netherlands, be=Belgium)
TARGET_COUNTRIES = ["gb", "de", "nl", "be"] 

# 🛑 THE BLACKLIST: Any job containing these words will be immediately skipped
EXCLUDED_TERMS = [
    "trade", "construction", "labour", "labor", "warehouse", 
    "driver", "operator", "technician", "mechanic", "picker", 
    "packer", "forklift", "plumber", "electrician", "retail"
]

def get_spreadsheet():
    """Connects securely to your Google Sheet master file."""
    print(f"Connecting to Google Cloud to access '{GOOGLE_SHEET_NAME}'...")
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME)

def apply_sleek_formatting(sheet):
    """Automatically styles the Google Sheet to look professional and organized."""
    try:
        print("  -> Applying sleek formatting to the sheet...")
        sheet.freeze(rows=1)
        # Apply dark background, bold white text, and center alignment to headers
        sheet.format('A1:G1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.22},
            "horizontalAlignment": "CENTER",
            "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "fontSize": 11, "bold": True}
        })
    except Exception as e:
        print(f"  -> Minor formatting error (safe to ignore): {e}")

def fetch_jobs_from_adzuna(country, search_term):
    """Fetches jobs directly from the Adzuna JSON API."""
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    
    if not app_id or not app_key:
        print("ERROR: Adzuna API credentials missing!")
        return []

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 50,
        "what": search_term,
        "content-type": "application/json"
    }

    print(f"  -> Querying API for '{search_term}' in '{country.upper()}'...")
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("results", [])
        return []
    except Exception:
        return []

def main():
    doc = get_spreadsheet()
    today_stamp = time.strftime("%Y-%m-%d")
    
    # Get or create the Discovery tab
    try:
        discovery_sheet = doc.worksheet(DISCOVERY_TAB)
    except gspread.exceptions.WorksheetNotFound:
        discovery_sheet = doc.add_worksheet(title=DISCOVERY_TAB, rows="1000", cols="7")
        
    # Set headers if empty
    if not discovery_sheet.get_all_values():
        discovery_sheet.append_row(["Job Title", "Company", "Location", "Category", "Status", "Link", "Date Discovered"])

    # Always ensure the formatting is applied
    apply_sleek_formatting(discovery_sheet)

    # Load existing URLs from Column F (Index 6) to prevent duplicates
    existing_links = set(discovery_sheet.col_values(6)) 
    
    rows_to_append = []
    total_added = 0
    total_blocked = 0

    for country in TARGET_COUNTRIES:
        print(f"\n--- Searching Country: {country.upper()} ---")
        for term in SEARCH_TERMS:
            jobs = fetch_jobs_from_adzuna(country, term)
            
            for job in jobs:
                job_url = job.get("redirect_url", "")
                
                # Check for duplicates
                if job_url and job_url not in existing_links:
                    title = job.get("title", "N/A").replace("<strong>", "").replace("</strong>", "")
                    company = job.get("company", {}).get("display_name", "Unknown")
                    location = job.get("location", {}).get("display_name", "Unknown")
                    category = job.get("category", {}).get("label", "N/A")
                    
                    # --- THE FILTER CHECK ---
                    title_lower = title.lower()
                    category_lower = category.lower()
                    
                    # If any blocked word is in the title OR category, skip it immediately
                    if any(bad_word in title_lower for bad_word in EXCLUDED_TERMS) or \
                       any(bad_word in category_lower for bad_word in EXCLUDED_TERMS):
                        total_blocked += 1
                        continue 
                    
                    # If it passes the filter, add it to our append list
                    rows_to_append.append([
                        title,
                        company,
                        location,
                        category,
                        "Not applied yet",
                        job_url,
                        today_stamp
                    ])
                    existing_links.add(job_url)
                    total_added += 1

    # ✨ THIS IS THE MAGIC LINE that automatically adds to the bottom ✨
    if rows_to_append:
        print(f"\nPushing {total_added} new discovered jobs to the bottom of the Google Sheet...")
        discovery_sheet.append_rows(rows_to_append)
    else:
        print("\nNo new unique jobs found today.")
        
    print(f"Done! Added {total_added} high-quality leads. Blocked {total_blocked} irrelevant jobs.")

if __name__ == "__main__":
    main()
