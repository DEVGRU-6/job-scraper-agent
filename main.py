import os
import json
import time
import sys
import requests
import gspread
from bs4 import BeautifulSoup
from google.genai import Client

sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀"
OVERVIEW_TAB = "Overview"

# Initialize Gemini Client
ai_client = Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

def get_spreadsheet():
    """Connects securely to your Google Sheet master file in the cloud."""
    print(f"Connecting to Google Cloud to access '{GOOGLE_SHEET_NAME}'...")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("CRITICAL: GOOGLE_CREDENTIALS environment variable is missing.")
        
    creds_dict = json.loads(creds_json)
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME)

def get_target_companies(doc):
    """Reads your Overview tab to dynamically discover companies and links."""
    print(f"Reading master directory from '{OVERVIEW_TAB}' tab...")
    try:
        overview = doc.worksheet(OVERVIEW_TAB)
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error: Could not find a tab named '{OVERVIEW_TAB}'. Check layout.")
        return []
        
    all_rows = overview.get_all_values()
    companies_list = []
    
    # Skip header rows
    for row in all_rows:
        # Assuming Company is in Col A [0] and Links in Col C [2] based on your setup
        if len(row) >= 3:
            company_name = row[0].strip()
            career_link = row[2].strip()
            
            if company_name and career_link.startswith("http"):
                companies_list.append({
                    "name": company_name,
                    "url": career_link
                })
                
    print(f"Found {len(companies_list)} target companies with career links to scan.")
    return companies_list

def scrape_career_site(url):
    """Fetches text contents from a target career page safely in the cloud."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract plain text, limit to 4000 chars to save Gemini tokens
            return soup.get_text(separator=' ', strip=True)[:4000]
        else:
            print(f"  -> Warning: Received status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"  -> Skipping network read for {url}: {e}")
    return ""

def analyze_jobs_with_ai(raw_html_text, company_name):
    """Uses Gemini to filter text for aviation/logistics roles for the company."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("  -> ERROR: GEMINI_API_KEY environment variable is missing.")
        return []

    prompt = f"""
    Analyze this web page text pulled from the career site of {company_name}.
    Identify specific job vacancies that meet ALL these criteria:
    1. Industry/Sector: Aviation, Aerospace, Airlines, Logistics, Consulting, Supply Chain, or Think Tanks.
    2. Category: Graduate schemes, Internships, Traineeships, Co-ops, or Master's Thesis tracks.
    3. Location: European Union (EU) or United Kingdom (UK).

    Format your response as a valid JSON list of objects. Each object MUST have these exact keys:
    "Title", "Location", "Type", "Link", "Deadline"

    Rules:
    - If no jobs match the criteria, return exactly an empty list: []
    - For fields like Deadline or Link not clearly visible in text, use "Not Listed".
    - Do not use markdown format wraps like ```json. Return purely the raw string array.

    Web Page Text:
    {raw_html_text}
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        clean_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_text)
    except Exception as e:
        print(f"  -> AI parsing error: {e}")
        return []

def main():
    try:
        doc = get_spreadsheet()
    except Exception as e:
        print(f"Failed to connect to Google Sheets: {e}")
        return

    targets = get_target_companies(doc)
    today_stamp = time.strftime("%Y-%m-%d")
    
    # Process the top 5 companies per run to avoid rate limits
    for target in targets[:5]:
        company = target["name"]
        url = target["url"]
        
        print(f"\n[{company}] Processing career site...")
        web_text = scrape_career_site(url)
        
        if not web_text:
            print("  -> Could not read data from portal. Moving on.")
            continue
            
        found_jobs = analyze_jobs_with_ai(web_text, company)
        print(f"  -> AI evaluated text. Found {len(found_jobs)} matching postings.")
        
        if not found_jobs:
            continue
            
        # Get or dynamically build the company-specific tab in Google Sheets
        try:
            target_sheet = doc.worksheet(company)
        except gspread.exceptions.WorksheetNotFound:
            print(f"  -> Creating a new dedicated tab for: '{company}'")
            target_sheet = doc.add_worksheet(title=company, rows="1000", cols="7")
            
        # Initialize headers to match your existing tracking style
        if not target_sheet.get_all_values():
            target_sheet.append_row(["Company / Role", "Deadline", "Location", "Type", "Status", "Link", "Notes"])
            
        added = 0
        # Optimization: Fetch Column A and convert to a SET for blazing fast duplicate checking
        existing_titles = set(target_sheet.col_values(1)) 
        
        rows_to_append = []
        
        for job in found_jobs:
            title = job.get("Title", "N/A").strip()
            
            # Check the fast set instead of searching a list
            if title and title not in existing_titles:
                rows_to_append.append([
                    title,
                    job.get("Deadline", "Not Listed"),
                    job.get("Location", "N/A"),
                    job.get("Type", "N/A"),
                    "Not applied yet", 
                    job.get("Link", url),
                    f"Scraped Date: {today_stamp}"
                ])
                # Add to set to prevent duplicates within the same run
                existing_titles.add(title)
                added += 1
                print(f"  -> Preparing to log: '{title}'")
                
        # Batch append rows to save Google Sheets API quota
        if rows_to_append:
            target_sheet.append_rows(rows_to_append)
                
        print(f"[{company}] Completed updates. Added {added} new rows to Google Sheets.")

if __name__ == "__main__":
    main()
