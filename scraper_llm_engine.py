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

def generic_scraper(url, keywords):
    """
    Uses Jina Reader to clean the page and OpenRouter LLMs to extract jobs.
    """
    # --- STEP 1: Jina Reader (Convert URL to Markdown) ---
    reader_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(reader_url, timeout=15)
        # We cap the content to avoid hitting model token limits
        content = response.text[:12000] 
    except Exception as e:
        print(f"Jina Reader Error: {e}")
        return pd.DataFrame()

    # --- STEP 2: OpenRouter API Call ---
    # OpenRouter uses the OpenAI-compatible SDK
    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    prompt = f"""
    Act as a job recruiter. I am interested in these topics: {keywords}.
    From the provided text, find all job openings that match these interests.
    
    Return ONLY a JSON object with a key 'jobs' containing a list of objects.
    Each object must have: 'title', 'location', and 'link'.
    If no jobs match, return {{"jobs": []}}.
    
    TEXT TO ANALYZE:
    {content}
    """

    try:
        chat = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            # Note: Not all free models support 'json_object' response_format, 
            # so we handle it via the prompt instructions primarily.
            response_format={ "type": "json_object" } 
        )
        
        # Parse result
        raw_content = chat.choices[0].message.content
        data = json.loads(raw_content)
        
        # Ensure we return a DataFrame even if empty
        jobs = data.get("jobs", [])
        return pd.DataFrame(jobs)

    except Exception as e:
        st.error(f"OpenRouter Error: {e}")
        return pd.DataFrame()
