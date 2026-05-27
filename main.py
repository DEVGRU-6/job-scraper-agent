import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
# Replace this with the exact name of your Google Sheet
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀" 

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

def get_google_sheet():
    """Connects to Google Sheets using GitHub Secrets."""
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    scope = ["https://google.com", "https://googleapis.com"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(GOOGLE_SHEET_NAME).sheet1

def scrape_jobs():
    """Scrapes raw job listings using Playwright."""
    jobs_data = []
    # Search URL combining aviation, logistics, and European regions
    search_url = "https://google.com"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new-page()
        page.goto(search_url, wait_until="networkidle")
        
        # Select individual job card elements from the page layout
        job_cards = page.locator("li").all()
        
        # Take the top 15 jobs found to analyze
        for card in job_cards[:15]:
            text = card.inner_text()
            if text:
                jobs_data.append(text)
                
        browser.close()
    return jobs_data

def analyze_with_ai(raw_job_text):
    """Uses Gemini to filter and structure target career opportunities."""
    prompt = f"""
    Analyze this raw job listing text. 
    Strictly filter for positions that meet ALL these criteria:
    1. Industry: Aviation, Aerospace, Airlines, Logistics, Supply Chain, or Freight Forwarding.
    2. Role Type: Graduate position, Internship, Co-op, or Master's Thesis project.
    3. Location: European Union (EU) countries or the United Kingdom (UK).

    If it does not match, reply with exactly: "SKIP".
    If it matches, return a clean JSON object with these keys: Title, Company, Location, Type (Graduate/Internship/Thesis), URL. Do not include markdown or backticks.

    Job Text:
    {raw_job_text}
    """
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if "SKIP" in result:
            return None
        return json.loads(result)
    except:
        return None

def main():
    print("Starting job scraper...")
    raw_jobs = scrape_jobs()
    print(f"Found {len(raw_jobs)} potential raw listings. Filtering with AI...")
    
    sheet = get_google_sheet()
    
    # Add headers if sheet is empty
    if not sheet.get_all_values():
        sheet.append_row(["Title", "Company", "Location", "Type", "URL"])

    added_count = 0
    for raw_job in raw_jobs:
        parsed_job = analyze_with_ai(raw_job)
        if parsed_job:
            sheet.append_row([
                parsed_job.get("Title"),
                parsed_job.get("Company"),
                parsed_job.get("Location"),
                parsed_job.get("Type"),
                parsed_job.get("URL", "N/A")
            ])
            added_count += 1
            
    print(f"Successfully processed and added {added_count} relevant target positions to your Google Sheet.")

if __name__ == "__main__":
    main()
