import os
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from datetime import datetime
from urllib.parse import urljoin

# 1. DATABASE CONNECTION
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables.")
    exit(1)

engine = create_engine(DB_URL)

def run_global_scan():
    with engine.connect() as conn:
        print("--- Starting 24h Global Scan ---")
        
        # 2. GET ALL USERS (Updated to fetch target_url)
        users = conn.execute(text("SELECT id, email, keywords, target_url FROM users")).fetchall()
        
        if not users:
            print("⚠️ No users found in database.")
            return

        for user_id, email, keywords, target_url in users:
            if not target_url or not keywords:
                print(f"⏩ Skipping {email}: URL or keywords missing.")
                continue

            print(f"🔎 Scanning {target_url} for {email} (Keywords: {keywords})")
            
            # 3. CLEAN UP OLD DATA
            # Optional: Deletes previous results for this user so the Excel stays fresh
            conn.execute(
                text("DELETE FROM daily_excel_data WHERE user_id = :uid"),
                {"uid": user_id}
            )
            
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(target_url, headers=headers, timeout=20)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 4. MATCHING LOGIC
                keyword_list = [k.strip().lower() for k in keywords.split(",")]
                matches_found = 0

                # We look at all links on the target company page
                for a in soup.find_all("a"):
                    job_title = a.get_text().strip()
                    job_link = a.get("href", "")
                    
                    # If any keyword matches the job title and the title is long enough to be real
                    if any(k in job_title.lower() for k in keyword_list) and len(job_title) > 3:
                        
                        # Ensure link is absolute (handles /jobs/123 -> https://company.com/jobs/123)
                        full_link = urljoin(target_url, job_link)

                        # 5. SAVE TO DATABASE
                        conn.execute(
                            text("""
                                INSERT INTO daily_excel_data 
                                (user_id, job_title, company_name, location, link, extracted_at) 
                                VALUES (:uid, :title, :company, :loc, :link, :now)
                            """),
                            {
                                "uid": user_id, 
                                "title": job_title,
                                "company": "Target Company", # You could extract this from the URL domain
                                "loc": "Check Link",
                                "link": full_link,
                                "now": datetime.now()
                            }
                        )
                        matches_found += 1
                
                conn.commit()
                print(f"✅ Successfully saved {matches_found} jobs for {email}")
                
            except Exception as e:
                print(f"❌ Error scanning for {email}: {str(e)}")

if __name__ == "__main__":
    run_global_scan()
    print("--- 24h Scan Complete ---")
