import os
import pandas as pd
from sqlalchemy import create_engine, text
from scraper_engine import smart_scraper

# 1. DATABASE CONNECTION
# This uses the environment variable you will set in GitHub Secrets
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL environment variable is not set!")

engine = create_engine(DB_URL)

def run_automated_scan():
    print(f"--- Starting Daily Scan: {pd.Timestamp.now()} ---")
    
    with engine.connect() as conn:
        # 2. GET ALL USERS AND THEIR PREFERENCES
        users_df = pd.read_sql("SELECT username, keywords FROM users", conn)
        
        for _, user in users_df.iterrows():
            username = user['username']
            keywords = [k.strip() for k in user['keywords'].split(",") if k.strip()]
            
            if not keywords:
                print(f"Skipping {username}: No keywords found.")
                continue

            # 3. GET URLS FOR THIS SPECIFIC USER
            urls_query = text("SELECT url FROM urls WHERE username = :u")
            user_urls = pd.read_sql(urls_query, conn, params={"u": username})['url'].tolist()

            if not user_urls:
                print(f"Skipping {username}: No URLs tracked.")
                continue

            print(f"Scanning for {username} with keywords: {keywords}")

            for url in user_urls:
                try:
                    # 4. RUN THE SCRAPER
                    # This uses your existing logic from scraper_engine.py
                    found_jobs_df = smart_scraper(url, keywords)

                    if not found_jobs_df.empty:
                        # Prepare data for the scan_results table
                        found_jobs_df['username'] = username
                        found_jobs_df['company_url'] = url
                        # Rename columns if necessary to match your SQL table
                        # Assuming smart_scraper returns 'Job Title'
                        if 'Job Title' in found_jobs_df.columns:
                            found_jobs_df = found_jobs_df.rename(columns={'Job Title': 'job_title'})

                        # Select only the columns that exist in your SQL table
                        upload_df = found_jobs_df[['username', 'job_title', 'company_url']]
                        
                        # 5. SAVE TO SUPABASE
                        upload_df.to_sql('scan_results', engine, if_exists='append', index=False)
                        print(f"  [+] Found {len(upload_df)} jobs at {url}")
                    else:
                        print(f"  [-] No matches at {url}")

                except Exception as e:
                    print(f"  [!] Error scanning {url} for {username}: {e}")

    print("--- Scan Complete ---")

if __name__ == "__main__":
    run_automated_scan()
