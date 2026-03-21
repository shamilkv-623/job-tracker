import openai
import requests
import pandas as pd
import json

# 1. OpenRouter Configuration
# Get your key from https://openrouter.ai/keys
OPENROUTER_API_KEY = "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"
# Example free model: "meta-llama/llama-3-8b-instruct:free" 
# Or low-cost: "openai/gpt-4o-mini"
MODEL_NAME = "meta-llama/llama-3.3-70b-instruct:free"


def ai_agent_scraper(url, keywords):
    """
    LAYER 2: Uses Jina Reader + Llama 3.3 to find jobs normal scraping missed.
    """
    # 1. Jina Reader (Convert URL to clean Markdown)
    reader_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(reader_url, timeout=15)
        content = response.text[:12000] # Stay within token limits
    except Exception as e:
        print(f"Jina Error: {e}")
        return pd.DataFrame()

    # 2. OpenRouter API Setup
    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    # We use a very strict prompt for the Free model
    prompt = f"""
    Find all job openings matching these interests: {keywords}.
    Return ONLY a JSON object with a key 'jobs' containing a list of objects.
    Each object must have: 'Title', 'Location', and 'Link'.
    
    TEXT:
    {content}
    """

    try:
        chat = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            # Note: response_format is used, but we handle the string just in case
            response_format={ "type": "json_object" } 
        )
        
        # 3. Robust JSON Parsing
        raw_content = chat.choices[0].message.content.strip()
        
        # Remove potential markdown backticks if the model adds them
        if raw_content.startswith("```"):
            raw_content = raw_content.split("json")[-1].split("```")[0].strip()
            
        data = json.loads(raw_content)
        jobs = data.get("jobs", [])
        
        return pd.DataFrame(jobs)

    except Exception as e:
        # Silently fail so the app continues to the next URL
        print(f"LLM Error on {url}: {e}")
        return pd.DataFrame()
