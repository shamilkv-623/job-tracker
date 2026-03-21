import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin

def scrape_jobs(url, keyword):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        jobs = []

        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            href = link.get("href")

            if text and href:
                full_link = urljoin(url, href)

                if keyword.lower() in text.lower():
                    jobs.append({
                        "Job Title": text,
                        "Application Link": full_link
                    })

        df = pd.DataFrame(jobs)

        if df.empty:
            return pd.DataFrame({"Message": ["No matching jobs found"]})

        return df.drop_duplicates()

    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})
