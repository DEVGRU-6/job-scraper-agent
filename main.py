import os
import json
import time
import sys
import requests
from bs4 import BeautifulSoup
import gspread
from google.genai import Client

sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀"
OVERVIEW_TAB = "Overview"

# Initialize Gemini Client
ai_client = Client(api_key=os.environ["GEMINI_API_KEY"])

def get_spreadsheet():
    """Connects securely to your Google Sheet master file."""
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME)

def get_target_companies(doc):
    """Reads your Overview tab to dynamically discover companies and links."""
    print("Reading master directory from 'Overview' tab...")
    try:
        overview = doc.worksheet(OVERVIEW_TAB)
    except Exception:
        print(f"Error: Could not find a tab named '{OVERVIEW_TAB}'. Check layout.")
        return []
        
    # Get all rows (Company in Col A, Links in Col C)
    all_rows = overview.get_all_values()
    companies_list = []
    
    # Skip header rows to find where the companies start (Row 10+ based on image)
    for row in all_rows:
        if len(row) >= 3:
            company_name = row[0].strip()
            career_link = row[2].strip()
            
            # Only track if it has a valid name and a working http link
            if company_name and career_link.startswith("http"):
                companies_list.append({
                    "name": company_name,
                    "url": career_link
                })
    print(f"Found {len(companies_list)} target companies with career links to scan.")
    return companies_list

def scrape_career_site(url):
    """Fetches text contents from a target career page safely in the cloud."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract plain text blocks from the page structure
            return soup.get_text(separator=' ', strip=True)[:4000]
    except Exception as e:
        print(f"Skipping network read for {url}: {e}")
    return ""

def analyze_jobs_with_ai(raw_html_text, company_name):
    """Uses Gemini to filter text for aviation/logistics roles for the company."""
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
    except:
        return []

def main():
    doc = get_spreadsheet()
    targets = get_target_companies(doc)
    
    today_stamp = time.strftime("%Y-%m-%d")
    
    # Process the top 5 companies per run to avoid rate limits
    for target in targets[:5]:
        company = target["name"]
        url = target["url"]
        
        print(f"\nProcessing career site for: {company}...")
        web_text = scrape_career_site(url)
        
        if not web_text:
            print(f"Could not read data from portal for {company}. Moving on.")
            continue
            
        found_jobs = analyze_jobs_with_ai(web_text, company)
        print(f"AI evaluated page text. Found {len(found_jobs)} matching postings for {company}.")
        
        if not found_jobs:
            continue
            
        # Get or dynamically build the company-specific tab
        try:
            target_sheet = doc.worksheet(company)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Creating a new dedicated tab for: '{company}'")
            target_sheet = doc.add_worksheet(title=company, rows="1000", cols="6")
            
        # Initialize headers if the company sheet is fresh/empty
        if not target_sheet.get_all_values():
            target_sheet.append_row(["Job Title", "Location", "Type", "Application Link", "Deadline", "Scraped Date"])
            
        added = 0
        existing_titles = target_sheet.col_values(1) # Read Column A to avoid duplicate lines
        
        for job in found_jobs:
            title = job.get("Title", "N/A")
            if title not in existing_titles:
                target_sheet.append_row([
                    title,
                    job.get("Location", "N/A"),
                    job.get("Type", "N/A"),
                    job.get("Link", url), # Use master portal url if deep job link is missing
                    job.get("Deadline", "Not Listed"),
                    today_stamp
                ])
                added += 1
                print(f" -> Logged: '{title}' into tab '{company}'")
                
        print(f"Completed {company} updates. Added {added} new rows.")

if __name__ == "__main__":
    main()
