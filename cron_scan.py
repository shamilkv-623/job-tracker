import os
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from datetime import datetime

# 1. DATABASE CONNECTION
# This uses the 'DATABASE_URL' secret you set in GitHub Actions
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables.")
    exit(1)

engine = create_engine(DB_URL)

def run_global_scan():
    with engine.connect() as conn:
        # 2. GET ALL USERS
        # We fetch every user who has defined keywords to monitor
        print("--- Starting 24h Global Scan ---")
        users = conn.execute(text("SELECT id, email, keywords FROM users")).fetchall()
        
        if not users:
            print("⚠️ No users found in database.")
            return

        for user_id, email, keywords in users:
            if not keywords:
                print(f"⏩ Skipping {email}: No keywords defined.")
                continue

            print(f"🔎 Scanning for {email} (Keywords: {keywords})")
            
            # 3. TARGET SOURCE
            # For now, we use a default. You can also add a 'target_url' column 
            # to your 'users' table to make this even more specific.
            target_url = "https://careers.google.com/jobs/results/" 
            
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(target_url, headers=headers, timeout=20)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 4. MATCHING LOGIC
                keyword_list = [k.strip().lower() for k in keywords.split(",")]
                matches_found = 0

                for a in soup.find_all("a"):
                    job_title = a.get_text().strip()
                    job_link = a.get("href", "")
                    
                    # If any keyword matches the job title
                    if any(k in job_title.lower() for k in keyword_list):
                        # Ensure link is absolute
                        if job_link.startswith("/"):
                            job_link = f"https://careers.google.com{job_link}"

                        # 5. SAVE TO DATABASE
                        # Matches your 'daily_excel_data' table schema
                        conn.execute(
                            text("""
                                INSERT INTO daily_excel_data 
                                (user_id, job_title, company_name, location, link, extracted_at) 
                                VALUES (:uid, :title, :company, :loc, :link, :now)
                            """),
                            {
                                "uid": user_id, 
                                "title": job_title,
                                "company": "Google (Example Source)", # You can make this dynamic
                                "loc": "Remote / Various",
                                "link": job_link,
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
