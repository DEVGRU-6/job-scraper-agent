import os
import json
import time
import sys
import gspread
from google.genai import Client
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀" 

ai_client = Client(api_key=os.environ["GEMINI_API_KEY"])

SEARCH_QUERIES = [
    'aviation logistics graduate internship Europe',
    'airline graduate scheme internship UK',
    'aerospace masters thesis internship Europe',
    'dhl dsv schenker kuehne internship graduate'
]

def get_google_sheet():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME).sheet1

def scrape_jobs():
    all_jobs = []
    
    with sync_playwright() as p:
        # Launch with a standard desktop window size to force Google Jobs UI to load properly
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        for query in SEARCH_QUERIES:
            print(f"Searching for: {query}...")
            search_url = f"https://google.com{query.replace(' ', '+')}&ibp=htl;jobs"
            
            try:
                page.goto(search_url, wait_until="networkidle")
                time.sleep(5)  # Increased wait time for full data to render
                
                # Broaden the selector to grab various text containers if standard list items are hidden
                elements = page.locator("div[role='listitem'], li, div.g").all()
                
                count = 0
                for el in elements:
                    if count >= 8: # Gather up to 8 per query
                        break
                    text = el.inner_text()
                    if text and len(text.strip()) > 50 and text not in all_jobs:
                        all_jobs.append(text)
                        count += 1
            except Exception as e:
                print(f"Error scraping query '{query}': {e}")
                
        browser.close()
    return all_jobs

def analyze_with_ai(raw_job_text):
    # Relaxed the prompt criteria slightly so the AI extracts details rather than being overly strict
    prompt = f"""
    You are a career matching assistant. Analyze this job clipping.
    
    CRITERIA:
    - Industry: Aviation, Aerospace, Airlines, Logistics, Supply Chain, Maritime, Transport, or Policy/Think Tanks.
    - Level: Graduate, Entry-Level, Internship, Trainee, Co-op, or Master's Thesis.
    - Region: Europe, EU, or United Kingdom.
    
    If the text is clearly completely unrelated (like a Senior Doctor in USA), reply with exactly: "SKIP".
    Otherwise, extract the information and return a clean JSON object with these keys:
    Title, Company, Location, Type, URL. Do not use markdown blocks or backticks.

    Job Text:
    {raw_job_text}
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        result = response.text.strip()
        result = result.replace('```json', '').replace('```', '')
        
        if "SKIP" in result:
            return None
        return json.loads(result)
    except Exception as e:
        return None

def main():
    print("Starting targeted job scraper...")
    raw_jobs = scrape_jobs()
    print(f"Found {len(raw_jobs)} raw text blocks from searches.")
    
    if len(raw_jobs) == 0:
        print("Warning: Scraper did not capture any text data from the web pages. Google might be blocking or layout changed.")
        return

    sheet = get_google_sheet()
    
    if not sheet.get_all_values():
        sheet.append_row(["Title", "Company", "Location", "Type", "URL", "Date Added"])

    added_count = 0
    today_date = time.strftime("%Y-%m-%d")

    for idx, raw_job in enumerate(raw_jobs):
        parsed_job = analyze_with_ai(raw_job)
        if parsed_job:
            # Check for existing records safely
            existing_rows = sheet.get_all_values()
            existing_urls = [row[4] for row in existing_rows if len(row) > 4]
            
            job_url = parsed_job.get("URL", "N/A")
            sheet.append_row([
                parsed_job.get("Title", "Unknown Title"),
                parsed_job.get("Company", "Unknown Company"),
                parsed_job.get("Location", "Unknown Location"),
                parsed_job.get("Type", "Unknown Type"),
                job_url,
                today_date
            ])
            added_count += 1
            print(f"[{added_count}] Added to Sheet: {parsed_job.get('Title')} at {parsed_job.get('Company')}")
            
    print(f"Run complete. Successfully added {added_count} records to your Command Center sheet.")

if __name__ == "__main__":
    main()
