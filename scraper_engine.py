import requests
from bs4 import BeautifulSoup
import pandas as pd
from scraper_llm_engine import ai_agent_scraper 

def is_relevant(text, keywords):
    """
    Checks if any keyword exists in the text. 
    Improved to handle case-sensitivity and whitespace better.
    """
    if not text:
        return False
    # Clean the text to remove multiple spaces/newlines
    clean_text = " ".join(text.split()).lower()
    return any(k.lower().strip() in clean_text for k in keywords)

def normal_layer_scrape(url, keywords):
    """
    LAYER 1: The Fast, Free BeautifulSoup Scraper.
    Scans the page for direct links containing your keywords.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # 1. Fetch page content
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Ensure the site didn't block us
        soup = BeautifulSoup(response.text, "html.parser")
        
        jobs = []

        # 2. Iterate through all links
        for link in soup.find_all("a", href=True):
            title_text = link.get_text(strip=True)
            
            # Use the relevance check on the visible link text
            if is_relevant(title_text, keywords) and len(title_text) > 8:
                href = link["href"]
                
                # Fix relative URLs (e.g., /careers/job-1 -> https://site.com/careers/job-1)
                if href.startswith("/"):
                    base_url = "/".join(url.split("/")[:3]) # Extracts protocol + domain
                    href = base_url.rstrip("/") + "/" + href.lstrip("/")
                elif not href.startswith("http"):
                    href = url.rstrip("/") + "/" + href.lstrip("/")
                
                jobs.append({
                    "Title": title_text,
                    "Location": "Check site",
                    "Link": href,
                    "Method": "Basic Scan" 
                })
        
        return pd.DataFrame(jobs)
        
    except Exception as e:
        print(f"Layer 1 error for {url}: {e}")
        return pd.DataFrame()

def smart_scraper(url, keywords):
    """
    THE COORDINATOR: Controls the 2-layer flow.
    """
    # 1. Attempt Layer 1 (Fast & Free)
    df = normal_layer_scrape(url, keywords)
    
    # 2. If Layer 1 finds nothing, call the LLM Specialist (Layer 2)
    if df.empty:
        # This will trigger the Jina Reader + Llama 3.3 logic
        df_ai = ai_agent_scraper(url, keywords)
        
        if not df_ai.empty:
            # Add metadata so you know it was found by the AI
            df_ai["Method"] = "AI Agent (Llama 3.3)"
            return df_ai
            
    return df
