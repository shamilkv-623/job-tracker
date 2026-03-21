import requests
from bs4 import BeautifulSoup
import pandas as pd
from scraper_llm_engine import ai_agent_scraper # Import your AI Layer

def is_relevant(text, keywords):
    if not text:
        return False
    text = text.lower()
    return any(k.lower() in text for k in keywords)

def normal_layer_scrape(url, keywords, company="Custom"):
    """LAYER 1: The Fast, Free BeautifulSoup Scraper."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            if is_relevant(text, keywords) and len(text) > 10:
                href = link["href"]
                if href.startswith("/"):
                    href = url.rstrip("/") + "/" + href.lstrip("/")
                
                jobs.append({
                    "Company": company,
                    "Title": text,
                    "Location": "Check site",
                    "Link": href,
                    "Method": "Normal" # Track which layer found it
                })
        return pd.DataFrame(jobs)
    except Exception:
        return pd.DataFrame()

def smart_scraper(url, keywords, company="Custom"):
    """The Coordinator: Tries Normal first, then AI Agent."""
    
    # 1. Try Normal Scraper (Layer 1)
    df = normal_layer_scrape(url, keywords, company)
    
    # 2. If Normal fails (df is empty), trigger AI Agent (Layer 2)
    if df.empty:
        # Note: ai_agent_scraper should be defined in scraper_llm_engine.py
        df_ai = ai_agent_scraper(url, keywords)
        
        if not df_ai.empty:
            df_ai["Company"] = company
            df_ai["Method"] = "AI Agent"
            return df_ai
            
    return df
