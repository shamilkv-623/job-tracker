import os
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

# Use the Secret from GitHub
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

def run_global_scan():
    with engine.connect() as conn:
        # 1. Get every user who has keywords set up
        users = conn.execute(text("SELECT id, email, keywords FROM users")).fetchall()
        
        for user_id, email, keywords in users:
            print(f"--- Scanning for {email} ---")
            
            # 2. Define where to look (e.g., a common job portal or their saved URL)
            target_url = "https://careers.google.com/jobs/results/" # Or a specific column in DB
            
            try:
                res = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 3. Find matches for THIS specific user's keywords
                found_jobs = []
                for a in soup.find_all("a"):
                    text_val = a.get_text().strip()
                    if any(k.strip().lower() in text_val.lower() for k in keywords.split(",")):
                        found_jobs.append(text_val)

                # 4. Save the results into the 'daily_excel_data' table
                for job in set(found_jobs):
                    conn.execute(
                        text("""INSERT INTO daily_excel_data (user_id, job_title, extracted_at) 
                                VALUES (:uid, :title, NOW())"""),
                        {"uid": user_id, "title": job}
                    )
                conn.commit()
                print(f"✅ Saved {len(found_jobs)} jobs for {email}")
                
            except Exception as e:
                print(f"❌ Error scanning for {email}: {e}")

if __name__ == "__main__":
    run_global_scan()
