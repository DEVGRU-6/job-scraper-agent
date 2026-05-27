import os
import json
import time
import sys
import gspread
from google.genai import Client
from jobspy import scrape_jobs

# Force UTF-8 handling for the command center emojis
sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURATION ---
GOOGLE_SHEET_NAME = "🧧Bub Jobs Command Center🍀" 

# Initialize Gemini Client
ai_client = Client(api_key=os.environ["GEMINI_API_KEY"])

def get_google_sheet():
    """Connects securely to your Google Sheet using GitHub Secrets."""
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    client = gspread.service_account_from_dict(creds_dict)
    return client.open(GOOGLE_SHEET_NAME).sheet1

def fetch_jobspy_listings():
    """Bypasses cloud blocks by fetching aggregated data from LinkedIn & Indeed."""
    print("Querying job boards for aviation and logistics roles...")
    try:
        # Pulls postings from major platforms without triggering headless browser walls
        jobs_df = scrape_jobs(
            site_name=["linkedin", "indeed"],
            search_term="aviation logistics graduate internship",
            location="Europe",
            results_wanted=25,
            hours_old=72, # Captures anything posted within the last 3 days
        )
        
        # Format rows into easy-to-read text snippets for the AI model
        formatted_list = []
        for _, row in jobs_df.iterrows():
            job_summary = f"Title: {row.get('title')}\nCompany: {row.get('company')}\nLocation: {row.get('location')}\nLink: {row.get('job_url')}\nDescription: {row.get('description')[:500]}"
            formatted_list.append(job_summary)
            
        return formatted_list
    except Exception as e:
        print(f"Aggregator error: {e}")
        return []

def analyze_with_ai(job_snippet):
    """Filters data blocks via Gemini to target aviation/logistics roles."""
    prompt = f"""
    You are an AI data sorting assistant. Analyze this job details block.
    
    CRITERIA FOR MATCHING:
    1. Industry: Aviation, Aerospace, Airlines, Logistics, Maritime, Freight, or Transport Supply Chain.
    2. Career Tier: Graduate roles, Internships, Traineeships, Co-ops, or Master's Thesis options.
    3. Location: European Union or United Kingdom.

    If it matches, extract the fields and return a raw JSON object with these keys:
    Title, Company, Location, Type, URL. Do not use any markdown formatting or backticks.
    
    If it fails the criteria (e.g. Senior Manager, USA location, IT consultant), reply exactly with: "SKIP"

    Job Text:
    {job_snippet}
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        result = response.text.strip().replace('```json', '').replace('```', '')
        
        if "SKIP" in result:
            return None
        return json.loads(result)
    except:
        return None

def main():
    raw_listings = fetch_jobspy_listings()
    print(f"Successfully retrieved {len(raw_listings)} job blocks from boards.")
    
    if not raw_listings:
        print("No job data pulled. Ending operation check.")
        return

    sheet = get_google_sheet()
    
    # Initialize header names if working with a fresh tab
    if not sheet.get_all_values():
        sheet.append_row(["Title", "Company", "Location", "Type", "URL", "Date Added"])

    added_count = 0
    today_stamp = time.strftime("%Y-%m-%d")

    for listing in raw_listings:
        parsed_job = analyze_with_ai(listing)
        if parsed_job:
            # Read column E to ensure we don't write duplicates
            existing_urls = sheet.col_values(5)
            target_url = parsed_job.get("URL", "N/A")
            
            if target_url not in existing_urls:
                sheet.append_row([
                    parsed_job.get("Title", "N/A"),
                    parsed_job.get("Company", "N/A"),
                    parsed_job.get("Location", "N/A"),
                    parsed_job.get("Type", "N/A"),
                    target_url,
                    today_stamp
                ])
                added_count += 1
                print(f"Successfully recorded: {parsed_job.get('Title')} at {parsed_job.get('Company')}")
                
    print(f"Run complete. Added {added_count} new filtered entries into your Command Center sheet.")

if __name__ == "__main__":
    main()
