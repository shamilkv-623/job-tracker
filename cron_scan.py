import os
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

# 1. Connect using the Secret you set in GitHub
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

def run_automation():
    with engine.connect() as conn:
        # 2. Fetch EVERY client's monitoring settings
        # Ensure your 'users' table has a 'target_url' and 'keywords' column
        users = conn.execute(text("SELECT id, email, keywords, target_url FROM users")).fetchall()

        for user_id, email, keywords, url in users:
            if not url: continue
            
            print(f"Running 24h update for: {email}")
            
            # 3. Perform the scrape
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 4. Check for matches and SAVE to a results table
                # This is what the client sees when they log in!
                for a in soup.find_all("a"):
                    job_title = a.get_text().strip()
                    if any(k.strip().lower() in job_title.lower() for k in keywords.split(",")):
                        conn.execute(
                            text("INSERT INTO scraped_results (user_id, job_title, found_at) VALUES (:uid, :title, NOW())"),
                            {"uid": user_id, "title": job_title}
                        )
                conn.commit()
            except Exception as e:
                print(f"Failed for {email}: {e}")

if __name__ == "__main__":
    run_automation()
