import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

# Get DB URL from GitHub Secrets
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)

def run_24h_excel_prep():
    with engine.connect() as conn:
        # Get all client URLs/Keywords
        users = conn.execute(text("SELECT id, keywords FROM users")).fetchall()
        
        for user_id, keywords in users:
            # --- YOUR SCRAPING LOGIC HERE ---
            # Example: jobs = my_scraper(keywords)
            
            # Save the new data to the DB
            # This ensures the "Excel Source" is always fresh
            conn.execute(
                text("INSERT INTO daily_excel_data (user_id, job_title) VALUES (:uid, :title)"),
                {"uid": user_id, "title": "Quantitative Researcher"}
            )
        conn.commit()

if __name__ == "__main__":
    run_24h_excel_prep()
