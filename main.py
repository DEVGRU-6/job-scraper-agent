import os
import json
import time
import sys
import requests
import csv
from bs4 import BeautifulSoup
from google.genai import Client

sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURATION ---
BASE_FILE_PREFIX = "🧧Bub Jobs Command Center🍀"
OVERVIEW_FILE = f"{BASE_FILE_PREFIX} - Overview.csv"

# Initialize Gemini Client
# Ensure your environment variable GEMINI_API_KEY is set
ai_client = Client(api_key=os.environ["GEMINI_API_KEY"])

def get_target_companies():
    """Reads the local Overview CSV to dynamically discover companies and links."""
    print(f"Reading master directory from '{OVERVIEW_FILE}'...")
    companies_list = []
    
    if not os.path.exists(OVERVIEW_FILE):
        print(f"Error: Could not find the file '{OVERVIEW_FILE}'. Please ensure it's in the same directory.")
        return companies_list

    try:
        with open(OVERVIEW_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            all_rows = list(reader)
            
            for row in all_rows:
                # Need at least 3 columns to extract Company (Col A) and Link (Col C)
                if len(row) >= 3:
                    company_name = row[0].strip()
                    career_link = row[2].strip()
                    
                    # Only track if it has a valid name and a working http link
                    if company_name and career_link.startswith("http"):
                        companies_list.append({
                            "name": company_name,
                            "url": career_link
                        })
    except Exception as e:
        print(f"Error reading {OVERVIEW_FILE}: {e}")

    print(f"Found {len(companies_list)} target companies with career links to scan.")
    return companies_list

def scrape_career_site(url):
    """Fetches text contents from a target career page safely."""
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
    except Exception as e:
        print(f"AI parsing error: {e}")
        return []

def main():
    targets = get_target_companies()
    if not targets:
        return
        
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
            
        # Sanitize company name to safely create file paths (avoid slashes etc.)
        safe_company_name = company.replace('/', '_').replace('\\', '_')
        target_csv_file = f"{BASE_FILE_PREFIX} - {safe_company_name}.csv"
            
        # Read existing titles to avoid duplication
        existing_titles = []
        file_exists = os.path.exists(target_csv_file)
        
        if file_exists:
            with open(target_csv_file, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:  # skip empty lines
                        existing_titles.append(row[0]) # Title is in Column A
        else:
            print(f"Creating a new dedicated CSV for: '{company}'")

        added = 0
        
        # Append to the CSV
        with open(target_csv_file, mode='a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Write headers if the file is brand new
            if not file_exists or not existing_titles:
                writer.writerow(["Job Title", "Location", "Type", "Application Link", "Deadline", "Scraped Date"])
                
            for job in found_jobs:
                title = job.get("Title", "N/A")
                if title not in existing_titles:
                    writer.writerow([
                        title,
                        job.get("Location", "N/A"),
                        job.get("Type", "N/A"),
                        job.get("Link", url), # Use master portal url if deep job link is missing
                        job.get("Deadline", "Not Listed"),
                        today_stamp
                    ])
                    added += 1
                    print(f" -> Logged: '{title}' into '{target_csv_file}'")
                
        print(f"Completed {company} updates. Added {added} new rows.")

if __name__ == "__main__":
    main()
