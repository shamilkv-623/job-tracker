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
    # This acts as the bridge for the LLM to 'see' the website content
    reader_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(reader_url, timeout=15)
        # We cap the content to 12,000 characters to stay within model limits
        content = response.text[:12000] 
    except Exception as e:
        print(f"Jina Reader Error: {e}")
        return pd.DataFrame()

    # 2. OpenRouter API Setup
    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    # 3. Enhanced Prompt for better Link extraction
    prompt = f"""
    Act as a job recruiter. I am interested in these topics: {keywords}.
    From the provided text, find all job openings that match these interests.
    
    IMPORTANT: 
    If a job link is relative (e.g., starts with '/'), you MUST prepend it with the base domain: {url}.
    
    Return ONLY a JSON object with a key 'jobs' containing a list of objects.
    Each object must have: 'Title', 'Location', and 'Link'.
    If no jobs match, return {{"jobs": []}}.
    
    TEXT TO ANALYZE:
    {content}
    """

    try:
        chat = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            # Note: We use json_object format for cleaner parsing
            response_format={ "type": "json_object" } 
        )
        
        # 4. Robust JSON Parsing
        raw_content = chat.choices[0].message.content.strip()
        
        # Remove potential markdown backticks if the model adds them
        if raw_content.startswith("```"):
            raw_content = raw_content.split("json")[-1].split("```")[0].strip()
            
        data = json.loads(raw_content)
        jobs = data.get("jobs", [])
        
        # Create DataFrame and add the identification method
        df = pd.DataFrame(jobs)
        if not df.empty:
            df["Method"] = "AI Agent (Llama 3.3)"
            
        return df

    except Exception as e:
        print(f"OpenRouter Error on {url}: {e}")
        return pd.DataFrame()
