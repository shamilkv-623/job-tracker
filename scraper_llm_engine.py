import openai
import requests

def generic_scraper(url, keywords):
    """
    Hybrid Scraper: Tries simple scraping first, 
    falls back to LLM if the site structure is complex or changed.
    """
    # 1. Try to get clean text from the URL
    # We use a 'Reader' API to strip away HTML junk for the LLM
    reader_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(reader_url, timeout=10)
        markdown_content = response.text[:15000] # Cap content to save API tokens
    except Exception as e:
        return pd.DataFrame({"Error": [f"Could not reach site: {e}"]})

    # 2. Call the LLM to find the jobs
    client = openai.OpenAI(api_key="YOUR_OPENAI_API_KEY")
    
    prompt = f"Extract all job postings matching these keywords: {keywords}. " \
             f"Return ONLY a JSON list of objects with keys: 'title', 'location', 'link'. " \
             f"Page Content: {markdown_content}"

    response = client.chat.completions.create(
        model="gpt-4o-mini", # Fast and cheap for this task
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )

    # 3. Parse JSON and return DataFrame
    import json
    raw_data = json.loads(response.choices[0].message.content)
    # Most LLMs return a dict, we want the list inside it
    jobs_list = raw_data.get("jobs", raw_data.get("postings", []))
    
    return pd.DataFrame(jobs_list)
