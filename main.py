import os
import json
import time
import sys
import gspread
from google.genai import Client
from playwright.sync_api import sync_playwright

# Force Python output to use UTF-8 for emoji handling
sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀" 

# Configure New Gemini API Client
ai_client = Client(api_key=os.environ["GEMINI_API_KEY"])

# --- TARGET SEARCH QUERIES ---
SEARCH_QUERIES = [
    '("Lufthansa" OR "Air France" OR "KLM" OR "British Airways" OR "IAG" OR "Ryanair" OR "EasyJet") ("graduate" OR "internship" OR "thesis") jobs Europe UK',
    '("DHL" OR "Kuehne+Nagel" OR "DB Schenker" OR "DSV" OR "Maersk" OR "FedEx") ("graduate" OR "internship" OR "thesis") jobs Europe UK',
    '("Airbus" OR "Rolls-Royce" OR "Safran" OR "Thales" OR "Leonardo") ("graduate" OR "internship" OR "thesis") jobs Europe UK',
    '("Eurocontrol" OR "EASA" OR "IATA" OR "CAPA Centre for Aviation" OR "Civil Aviation Authority") ("traineeship" OR "internship" OR "graduate") jobs'
]

def get_google_sheet():
    """Connects to Google Sheets cleanly using modern service account method."""
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    # Modern gspread allows direct authentication from the service dictionary
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME).sheet1

def scrape_jobs():
    """Scrapes job listings with corrected search engine URL formatting."""
    all_jobs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for query in SEARCH_QUERIES:
            print(f"Searching for: {query}...")
            # FIXED: Added the critical missing '/search?q=' structure
            search_url = f"https://google.com{query.replace(' ', '+')}&ibp=htl;jobs"
            
            try:
                page.goto(search_url, wait_until="networkidle")
                time.sleep(3) # Safe buffer for loading elements
                
                job_cards = page.locator("li").all()
                for card in job_cards[:5]:
                    text = card.inner_text()
                    if text:
                        all_jobs.append(text)
            except Exception as e:
                print(f"Error scraping query '{query}': {e}")
                
        browser.close()
    return all_jobs

def analyze_with_ai(raw_job_text):
    """Uses Gemini to filter specifically for your target sectors."""
    prompt = f"""
    Analyze this job listing text. 
    Strictly filter for positions that meet ALL these criteria:
    1. Industry: Aviation, Aerospace, Airlines, Logistics, Supply Chain, or Aviation Policy/Think Tanks.
    2. Role Type: Graduate scheme, Internship, Co-op, Traineeship, or Master's Thesis.
    3. Location: EU countries or UK.

    If it matches, return a clean JSON object with these keys: 
    Title, Company, Location, Type (Graduate/Internship/Thesis), URL.
    
    If it DOES NOT match (e.g. Senior role, wrong industry, USA only), reply exactly: "SKIP".
    
    Job Text:
    {raw_job_text}
    """
    try:
        # Modernized text invocation structure for Gemini
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        result = response.text.strip()
        result = result.replace('```json', '').replace('```', '')
        
        if "SKIP" in result:
            return None
        return json.loads(result)
    except:
        return None

def main():
    print("Starting targeted job scraper...")
    raw_jobs = scrape_jobs()
    print(f"Found {len(raw_jobs)} potential listings across all sectors. Filtering with AI...")
    
    sheet = get_google_sheet()
    
    if not sheet.get_all_values():
        sheet.append_row(["Title", "Company", "Location", "Type", "URL", "Date Added"])

    added_count = 0
    today_date = time.strftime("%Y-%m-%d")

    for raw_job in raw_jobs:
        parsed_job = analyze_with_ai(raw_job)
        if parsed_job:
            existing_urls = sheet.col_values(5)
            if parsed_job.get("URL", "N/A") not in existing_urls:
                sheet.append_row([
                    parsed_job.get("Title"),
                    parsed_job.get("Company"),
                    parsed_job.get("Location"),
                    parsed_job.get("Type"),
                    parsed_job.get("URL", "N/A"),
                    today_date
                ])
                added_count += 1
                print(f"Added: {parsed_job.get('Title')} at {parsed_job.get('Company')}")
            
    print(f"Run complete. Added {added_count} new relevant positions.")

if __name__ == "__main__":
    main()
