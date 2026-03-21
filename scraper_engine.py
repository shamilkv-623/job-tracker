import requests
from bs4 import BeautifulSoup
import pandas as pd

def is_relevant(text, keywords):
    if not text:
        return False
    text = text.lower()
    return any(k in text for k in keywords)

def generic_scraper(url, keywords, company="Custom"):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        jobs = []

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)

            if is_relevant(text, keywords) and len(text) > 10:
                href = link["href"]

                if href.startswith("/"):
                    href = url.rstrip("/") + href

                jobs.append({
                    "Company": company,
                    "Title": text,
                    "Location": "Check site",
                    "Link": href
                })

        return pd.DataFrame(jobs)

    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})
